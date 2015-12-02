# Copyright (c) 2012-2015 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#

import galsim
import logging

# The items in each tuple are:
#   - The function to call to build the image
#   - The function to call to get the number of objects that will be built
valid_image_types = {
    'Single' : ( 'SetupSingleImage', 'BuildSingleImage', None, 'GetNObjForSingleImage' ),
    'Tiled' : ( 'SetupTiledImage', 'BuildTiledImage', 'AddNoiseTiledImage',
                'GetNObjForTiledImage' ),
    'Scattered' : ( 'SetupScatteredImage', 'BuildScatteredImage', 'AddNoiseScatteredImage',
                    'GetNObjForScatteredImage' ),
}


def BuildImages(nimages, config, nproc=1, logger=None, image_num=0, obj_num=0):
    """
    Build a number of postage stamp images as specified by the config dict.

    @param nimages             How many images to build.
    @param config              A configuration dict.
    @param nproc               How many processes to use. [default: 1]
    @param logger              If given, a logger object to log progress. [default: None]
    @param image_num           If given, the current `image_num` [default: 0]
    @param obj_num             If given, the current `obj_num` [default: 0]

    @returns a list of images
    """
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('file %d: BuildImages nimages = %d: image, obj = %d,%d',
                     config.get('file_num',0),nimages,image_num,obj_num)

    import time
    def worker(input, output, config, logger):
        proc = current_process().name
        for job in iter(input.get, 'STOP'):
            try :
                (image_num, obj_num, nim, info) = job
                if logger and logger.isEnabledFor(logging.DEBUG):
                    logger.debug('%s: Received job to do %d images, starting with %d',
                                 proc,nim,image_num)
                results = []
                for k in range(nim):
                    t1 = time.time()
                    im = BuildImage(config, image_num=image_num, obj_num=obj_num, logger=logger)
                    obj_num += galsim.config.GetNObjForImage(config, image_num)
                    image_num += 1
                    t2 = time.time()
                    results.append( (im, t2-t1) )
                    ys, xs = im[0].array.shape
                    if logger and logger.isEnabledFor(logging.INFO):
                        logger.info('%s: Image %d: size = %d x %d, time = %f sec',
                                    proc, image_num, xs, ys, t2-t1)
                output.put( (results, info, proc) )
                if logger and logger.isEnabledFor(logging.DEBUG):
                    logger.debug('%s: Finished job %d -- %d',proc,image_num-nim,image_num-1)
            except Exception as e:
                import traceback
                tr = traceback.format_exc()
                if logger and logger.isEnabledFor(logging.DEBUG):
                    logger.debug('%s: Caught exception %s\n%s',proc,str(e),tr)
                output.put( (e, info, tr) )

    nproc = galsim.config.UpdateNProc(nproc,logger)

    if nproc > 1 and 'current_nproc' in config:
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug("Already multiprocessing.  Ignoring nproc for image processing")
        nproc = 1

    if nproc > nimages:
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug("There are only %d images.  Reducing nproc to %d."%(nimages,nimages))
        nproc = nimages

    if nproc > 1:
        if logger and logger.isEnabledFor(logging.WARN):
            logger.warn("Using %d processes for image processing",nproc)

        from multiprocessing import Process, Queue, current_process
        from multiprocessing.managers import BaseManager

        # Initialize the images list to have the correct size.
        # This is important here, since we'll be getting back images in a random order,
        # and we need them to go in the right places (in order to have deterministic
        # output files).  So we initialize the list to be the right size.
        images = [ None for i in range(nimages) ]

        # Number of images to do in each task:
        # At most nimages / nproc.
        # At least 1 normally, but number in Ring if doing a Ring test
        # Shoot for gemoetric mean of these two.
        max_nim = nimages / nproc
        min_nim = 1
        if ( ('image' not in config or 'type' not in config['image'] or
                 config['image']['type'] == 'Single') and
             'gal' in config and isinstance(config['gal'],dict) and 'type' in config['gal'] and
             config['gal']['type'] == 'Ring' and 'num' in config['gal'] ):
            min_nim = galsim.config.ParseValue(config['gal'], 'num', config, int)[0]
            if logger and logger.isEnabledFor(logging.DEBUG):
                logger.debug('file %d: Found ring: num = %d',config.get('file_num',0),min_nim)
        if max_nim < min_nim:
            nim_per_task = min_nim
        else:
            import math
            # This formula keeps nim a multiple of min_nim, so Rings are intact.
            nim_per_task = min_nim * int(math.sqrt(float(max_nim) / float(min_nim)))
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug('file %d: nim_per_task = %d',config.get('file_num',0),nim_per_task)

        # Set up the task list
        task_queue = Queue()
        for k in range(0,nimages,nim_per_task):
            nim1 = min(nim_per_task, nimages-k)
            task_queue.put( ( image_num+k, obj_num, nim1, k ) )
            for i in range(nim1):
                obj_num += galsim.config.GetNObjForImage(config, image_num+k+i)

        # Run the tasks
        # Each Process command starts up a parallel process that will keep checking the queue
        # for a new task. If there is one there, it grabs it and does it. If not, it waits
        # until there is one to grab. When it finds a 'STOP', it shuts down.
        done_queue = Queue()
        p_list = []
        import copy
        config1 = galsim.config.CopyConfig(config)
        config1['current_nproc'] = nproc
        logger_proxy = galsim.config.GetLoggerProxy(logger)
        for j in range(nproc):
            p = Process(target=worker, args=(task_queue, done_queue, config1, logger_proxy),
                        name='Process-%d'%(j+1))
            p.start()
            p_list.append(p)

        # In the meanwhile, the main process keeps going.  We pull each set of images off of the
        # done_queue and put them in the appropriate place in the lists.
        # This loop is happening while the other processes are still working on their tasks.
        # You'll see that these logging statements get printed out as the stamp images are still
        # being drawn.
        for i in range(0,nimages,nim_per_task):
            results, k0, proc = done_queue.get()
            if isinstance(results,Exception):
                # results is really the exception, e
                # proc is really the traceback
                if logger:
                    logger.error('Exception caught during job starting with image %d', k0)
                    logger.error('%s',proc)
                    logger.error('Aborting the rest of this file')
                for j in range(nproc):
                    p_list[j].terminate()
                raise results
            k = k0
            for result in results:
                images[k] = result[0]
                k += 1
            if logger and logger.isEnabledFor(logging.DEBUG):
                logger.debug('%s: Successfully returned results for images %d--%d', proc, k0, k-1)

        # Stop the processes
        # The 'STOP's could have been put on the task list before starting the processes, or you
        # can wait.  In some cases it can be useful to clear out the done_queue (as we just did)
        # and then add on some more tasks.  We don't need that here, but it's perfectly fine to do.
        # Once you are done with the processes, putting nproc 'STOP's will stop them all.
        # This is important, because the program will keep running as long as there are running
        # processes, even if the main process gets to the end.  So you do want to make sure to
        # add those 'STOP's at some point!
        for j in range(nproc):
            task_queue.put('STOP')
        for j in range(nproc):
            p_list[j].join()
        task_queue.close()

    else : # nproc == 1

        images = []

        for k in range(nimages):
            t1 = time.time()
            image = BuildImage(config, image_num=image_num, obj_num=obj_num, logger=logger)
            images += [ image ]
            t2 = time.time()
            if logger and logger.isEnabledFor(logging.INFO):
                # Note: numpy shape is y,x
                ys, xs = image.array.shape
                logger.info('Image %d: size = %d x %d, time = %f sec', image_num, xs, ys, t2-t1)
            obj_num += galsim.config.GetNObjForImage(config, image_num)
            image_num += 1

    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('file %d: Done making images %d--%d',config.get('file_num',0),
                     image_num,image_num+nimages-1)

    return images


def SetupConfigImageNum(config, image_num, obj_num):
    """Do the basic setup of the config dict at the image processing level.

    Includes:
    - Set config['image_num'] = image_num
    - Set config['obj_num'] = obj_num
    - Set config['index_key'] = 'image_num'
    - Make sure config['image'] exists
    - Set config['image']['draw_method'] to 'auto' if not given.

    @param config           A configuration dict.
    @param image_num        The current image_num.
    @param obj_num          The current obj_num.
    """
    config['image_num'] = image_num
    config['obj_num'] = obj_num
    config['index_key'] = 'image_num'

    # Make config['image'] exist if it doesn't yet.
    if 'image' not in config:
        config['image'] = {}
    image = config['image']
    if not isinstance(image, dict):
        raise AttributeError("config.image is not a dict.")

    if 'draw_method' not in image:
        image['draw_method'] = 'auto'
    if 'type' not in image:
        image['type'] = 'Single'


def SetupConfigImageSize(config, xsize, ysize):
    """Do some further setup of the config dict at the image processing level based on
    the provided image size.

    - Set config['image_xsize'], config['image_ysize'] to the size of the image
    - Set config['image_origin'] to the origin of the image
    - Set config['image_center'] to the center of the image
    - Set config['image_bounds'] to the bounds of the image
    - Build the WCS based on either config['image']['wcs'] or config['image']['pixel_scale']
    - Set config['wcs'] to be the built wcs
    - If wcs.isPixelScale(), also set config['pixel_scale'] for convenience.

    @param config           A configuration dict.
    @param xsize            The size of the image in the x-dimension.
    @param ysize            The size of the image in the y-dimension.
    """
    config['image_xsize'] = xsize
    config['image_ysize'] = ysize

    origin = 1 # default
    if 'index_convention' in config['image']:
        convention = galsim.config.ParseValue(config['image'],'index_convention',config,str)[0]
        if convention.lower() in [ '0', 'c', 'python' ]:
            origin = 0
        elif convention.lower() in [ '1', 'fortran', 'fits' ]:
            origin = 1
        else:
            raise AttributeError("Unknown index_convention: %s"%convention)

    config['image_origin'] = galsim.PositionI(origin,origin)
    config['image_center'] = galsim.PositionD( origin + (xsize-1.)/2., origin + (ysize-1.)/2. )
    config['image_bounds'] = galsim.BoundsI(origin, origin+xsize-1, origin, origin+ysize-1)

    # Build the wcs
    wcs = galsim.config.BuildWCS(config)
    config['wcs'] = wcs

    # If the WCS is a PixelScale or OffsetWCS, then store the pixel_scale in base.  The
    # config apparatus does not use it -- we always use the wcs -- but we keep it in case
    # the user wants to use it for an Eval item.  It's one of the variables they are allowed
    # to assume will be present for them.
    if wcs.isPixelScale():
        config['pixel_scale'] = wcs.scale


def BuildImage(config, logger=None, image_num=0, obj_num=0):
    """
    Build an Image according to the information in config.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress. [default: None]
    @param image_num           If given, the current `image_num` [default: 0]
    @param obj_num             If given, the current `obj_num` [default: 0]

    @returns the final image
    """
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: BuildImage: image, obj = %d,%d',image_num,image_num,obj_num)

    if 'image' in config and 'type' in config['image']:
        image_type = config['image']['type']
    else:
        image_type = 'Single'

    if image_type not in valid_image_types:
        raise AttributeError("Invalid image.type=%s."%image_type)

    # Setup basic things in the top-level config dict that we will need.
    SetupConfigImageNum(config,image_num,obj_num)

    # Build the rng to use at the image level.
    seed = galsim.config.SetupConfigRNG(config)
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: seed = %d',image_num,seed)
    rng = config['rng'] # Grab this for use later

    # Do the necessary initial setup for this image type.
    setup_func = eval(valid_image_types[image_type][0])
    xsize, ysize = setup_func(config, logger, image_num, obj_num)

    # Given this image size (which may be 0,0, in which case it will be set automatically later),
    # do some basic calculations
    SetupConfigImageSize(config,xsize,ysize)
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: image_size = %d, %d',image_num,xsize,ysize)
        logger.debug('image %d: image_origin = %s',image_num,config['image_origin'])
        logger.debug('image %d: image_center = %s',image_num,config['image_center'])

    # Sometimes an input field needs to do something special at the start of an image.
    galsim.config.SetupInputsForImage(config,logger)

    # Likewise for the extra output items.
    galsim.config.SetupExtraOutputsForImage(config,logger)

    # Actually build the image now.  This is the main working part of this function.
    # It calls out to the appropriate build function for this image type.
    build_func = eval(valid_image_types[image_type][1])
    image = build_func(config, logger, image_num, obj_num)

    # Store the current image in the base-level config for reference
    config['current_image'] = image

    # Mark that we are no longer doing a single galaxy by deleting image_pos from config top
    # level, so it cannot be used for things like wcs.pixelArea(image_pos).
    if 'image_pos' in config: del config['image_pos']

    # Put the rng back into config['rng'] for use by the AddNoise function.
    config['rng'] = rng

    # Do whatever processing is required for the extra output items.
    galsim.config.ProcessExtraOutputsForImage(config,logger)

    noise_func = valid_image_types[image_type][2]
    if noise_func:
        noise_func = eval(noise_func)
        noise_func(config, logger, image_num, obj_num)

    return image


# Ignore these when parsing the parameters for specific Image types:
image_ignore = [ 'random_seed', 'draw_method', 'noise', 'pixel_scale', 'wcs',
                 'sky_level', 'sky_level_pixel', 'index_convention', 'nproc',
                 'retry_failures', 'n_photons', 'wmult', 'offset', 'gsparams' ]


def SetupSingleImage(config, logger, image_num, obj_num):
    """
    Do the initialization and setup for building a Single image.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`
    @param obj_num             If given, the current `obj_num`

    @returns the (blank) image object
    """
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: BuildSingleImage: image, obj = %d,%d',image_num,image_num,obj_num)

    extra_ignore = [ 'image_pos', 'world_pos' ]
    opt = { 'size' : int , 'xsize' : int , 'ysize' : int }
    params = galsim.config.GetAllParams(
        config['image'], 'image', config, opt=opt, ignore=image_ignore+extra_ignore)[0]

    # If image_force_xsize and image_force_ysize were set in config, this overrides the
    # read-in params.
    if 'image_force_xsize' in config and 'image_force_ysize' in config:
        xsize = config['image_force_xsize']
        ysize = config['image_force_ysize']
    else:
        size = params.get('size',0)
        xsize = params.get('xsize',size)
        ysize = params.get('ysize',size)
    if (xsize == 0) != (ysize == 0):
        raise AttributeError(
            "Both (or neither) of image.xsize and image.ysize need to be defined  and != 0.")

    # We allow world_pos to be in config[image], but we don't want it to lead to a final_shift
    # in BuildSingleStamp.  The easiest way to do this is to set image_pos to (0,0).
    if 'world_pos' in config['image']:
        config['image']['image_pos'] = (0,0)

    return xsize, ysize


def BuildSingleImage(config, logger, image_num, obj_num):
    """
    Build an Image consisting of a single stamp.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`
    @param obj_num             If given, the current `obj_num`

    @returns the final image
    """
    xsize = config['image_xsize']
    ysize = config['image_ysize']

    image, current_var = galsim.config.BuildSingleStamp(
            config, xsize=xsize, ysize=ysize, obj_num=obj_num,
            do_noise=True, logger=logger)

    return image


def SetupTiledImage(config, logger, image_num, obj_num):
    """
    Build an Image consisting of a tiled array of postage stamps.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`.
    @param obj_num             If given, the current `obj_num`.

    @returns the final image
    """
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: BuildTiledImage: image, obj = %d,%d',image_num,image_num,obj_num)

    extra_ignore = [ 'image_pos' ] # We create this below, so on subequent passes, we ignore it.
    req = { 'nx_tiles' : int , 'ny_tiles' : int }
    opt = { 'stamp_size' : int , 'stamp_xsize' : int , 'stamp_ysize' : int ,
            'border' : int , 'xborder' : int , 'yborder' : int , 'order' : str }
    params = galsim.config.GetAllParams(
        config['image'], 'image', config, req=req, opt=opt, ignore=image_ignore+extra_ignore)[0]

    nx_tiles = params['nx_tiles']
    ny_tiles = params['ny_tiles']
    config['nx_tiles'] = nx_tiles
    config['ny_tiles'] = ny_tiles
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: n_tiles = %d, %d',image_num,nx_tiles,ny_tiles)

    stamp_size = params.get('stamp_size',0)
    stamp_xsize = params.get('stamp_xsize',stamp_size)
    stamp_ysize = params.get('stamp_ysize',stamp_size)
    config['tile_xsize'] = stamp_xsize
    config['tile_ysize'] = stamp_ysize

    if (stamp_xsize == 0) or (stamp_ysize == 0):
        raise AttributeError(
            "Both image.stamp_xsize and image.stamp_ysize need to be defined and != 0.")

    border = params.get("border",0)
    xborder = params.get("xborder",border)
    yborder = params.get("yborder",border)

    do_noise = xborder >= 0 and yborder >= 0
    # TODO: Note: if one of these is < 0 and the other is > 0, then
    #       this will add noise to the border region.  Not exactly the
    #       design, but I didn't bother to do the bookkeeping right to
    #       make the borders pure 0 in that case.
    config['do_noise_in_stamps'] = do_noise

    full_xsize = (stamp_xsize + xborder) * nx_tiles - xborder
    full_ysize = (stamp_ysize + yborder) * ny_tiles - yborder

    config['tile_xborder'] = xborder
    config['tile_yborder'] = yborder

    # If image_force_xsize and image_force_ysize were set in config, make sure it matches.
    if ( ('image_force_xsize' in config and full_xsize != config['image_force_xsize']) or
         ('image_force_ysize' in config and full_ysize != config['image_force_ysize']) ):
        raise ValueError(
            "Unable to reconcile required image xsize and ysize with provided "+
            "nx_tiles=%d, ny_tiles=%d, "%(nx_tiles,ny_tiles) +
            "xborder=%d, yborder=%d\n"%(xborder,yborder) +
            "Calculated full_size = (%d,%d) "%(full_xsize,full_ysize)+
            "!= required (%d,%d)."%(config['image_force_xsize'],config['image_force_ysize']))

    return full_xsize, full_ysize


def BuildTiledImage(config, logger, image_num, obj_num):
    """
    Build an Image consisting of a tiled array of postage stamps.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`.
    @param obj_num             If given, the current `obj_num`.

    @returns the final image
    """
    full_xsize = config['image_xsize']
    full_ysize = config['image_ysize']
    wcs = config['wcs']

    full_image = galsim.ImageF(full_xsize, full_ysize)
    full_image.setOrigin(config['image_origin'])
    full_image.wcs = wcs
    full_image.setZero()

    if 'nproc' in config['image']:
        nproc = galsim.config.ParseValue(config['image'],'nproc',config,int)[0]
    else:
        nproc = 1

    do_noise = config['do_noise_in_stamps']
    xsize = config['tile_xsize']
    ysize = config['tile_ysize']
    xborder = config['tile_xborder']
    yborder = config['tile_yborder']

    nx_tiles = config['nx_tiles']
    ny_tiles = config['ny_tiles']
    nobjects = nx_tiles * ny_tiles

    # Make a list of ix,iy values according to the specified order:
    if 'order' in config['image']:
        order = galsim.config.ParseValue(config['image'],'order',config,str)[0].lower()
    else:
        order = 'row'
    if order.startswith('row'):
        ix_list = [ ix for iy in range(ny_tiles) for ix in range(nx_tiles) ]
        iy_list = [ iy for iy in range(ny_tiles) for ix in range(nx_tiles) ]
    elif order.startswith('col'):
        ix_list = [ ix for ix in range(nx_tiles) for iy in range(ny_tiles) ]
        iy_list = [ iy for ix in range(nx_tiles) for iy in range(ny_tiles) ]
    elif order.startswith('rand'):
        ix_list = [ ix for ix in range(nx_tiles) for iy in range(ny_tiles) ]
        iy_list = [ iy for ix in range(nx_tiles) for iy in range(ny_tiles) ]
        rng = config['rng']
        galsim.random.permute(rng, ix_list, iy_list)
    else:
        raise ValueError("Invalid order.  Must be row, column, or random")

    # Define a 'image_pos' field so the stamps can set their position appropriately in case
    # we need it for PowerSpectum or NFWHalo.
    x0 = (xsize-1)/2. + config['image_origin'].x
    y0 = (ysize-1)/2. + config['image_origin'].y
    dx = xsize + xborder
    dy = ysize + yborder
    config['image']['image_pos'] = {
        'type' : 'XY' ,
        'x' : { 'type' : 'List',
                'items' : [ x0 + ix*dx for ix in ix_list ]
              },
        'y' : { 'type' : 'List',
                'items' : [ y0 + iy*dy for iy in iy_list ]
              }
    }

    stamps, current_vars = galsim.config.BuildStamps(
            nobjects, config, nproc=nproc, logger=logger, obj_num=obj_num,
            xsize=xsize, ysize=ysize, do_noise=do_noise)

    for k in range(nobjects):
        # This is our signal that the object was skipped.
        if not stamps[k].bounds.isDefined(): continue
        if False:
            logger.debug('image %d: full bounds = %s',image_num,str(full_image.bounds))
            logger.debug('image %d: stamp %d bounds = %s',image_num,k,str(stamps[k].bounds))
        assert full_image.bounds.includes(stamps[k].bounds)
        b = stamps[k].bounds
        full_image[b] += stamps[k]

    current_var = 0
    if not do_noise:
        if 'noise' in config['image']:
            # First bring the image so far up to a flat noise variance
            current_var = FlattenNoiseVariance(config, full_image, stamps, current_vars, logger)
    config['current_var'] = current_var
    return full_image


def AddNoiseTiledImage(config, logger, image_num, obj_num):
    """
    Add the final noise to a Tiled image

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`.
    @param obj_num             If given, the current `obj_num`.
    """
    # If didn't do noise above in the stamps, then need to do it here.
    do_noise = config['do_noise_in_stamps']
    if not do_noise:
        # Apply the sky and noise to the full image
        full_image = config['current_image']
        galsim.config.AddSky(config,full_image)
        if 'noise' in config['image']:
            current_var = config['current_var']
            galsim.config.AddNoise(config,full_image,current_var,logger)


def SetupScatteredImage(config, logger, image_num, obj_num):
    """
    Build an Image containing multiple objects placed at arbitrary locations.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`
    @param obj_num             If given, the current `obj_num`

    @returns the final image
    """
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: BuildScatteredImage: image, obj = %d,%d',
                     image_num,image_num,obj_num)

    if 'nobjects' not in config['image']:
        nobjects = galsim.config.ProcessInputNObjects(config)
        if nobjects is None:
            raise AttributeError("Attribute nobjects is required for image.type = Scattered")
    else:
        nobjects = galsim.config.ParseValue(config['image'],'nobjects',config,int)[0]
    if logger and logger.isEnabledFor(logging.DEBUG):
        logger.debug('image %d: nobj = %d',image_num,nobjects)
    config['nobjects'] = nobjects

    # These are allowed for Scattered, but we don't use them here.
    extra_ignore = [ 'image_pos', 'world_pos', 'stamp_size', 'stamp_xsize', 'stamp_ysize',
                     'nobjects' ]
    opt = { 'size' : int , 'xsize' : int , 'ysize' : int }
    params = galsim.config.GetAllParams(
        config['image'], 'image', config, opt=opt, ignore=image_ignore+extra_ignore)[0]

    # Special check for the size.  Either size or both xsize and ysize is required.
    if 'size' not in params:
        if 'xsize' not in params or 'ysize' not in params:
            raise AttributeError(
                "Either attribute size or both xsize and ysize required for image.type=Scattered")
        full_xsize = params['xsize']
        full_ysize = params['ysize']
    else:
        if 'xsize' in params:
            raise AttributeError(
                "Attributes xsize is invalid if size is set for image.type=Scattered")
        if 'ysize' in params:
            raise AttributeError(
                "Attributes ysize is invalid if size is set for image.type=Scattered")
        full_xsize = params['size']
        full_ysize = params['size']

    # If image_force_xsize and image_force_ysize were set in config, make sure it matches.
    if ( ('image_force_xsize' in config and full_xsize != config['image_force_xsize']) or
         ('image_force_ysize' in config and full_ysize != config['image_force_ysize']) ):
        raise ValueError(
            "Unable to reconcile required image xsize and ysize with provided "+
            "xsize=%d, ysize=%d, "%(full_xsize,full_ysize))

    return full_xsize, full_ysize


def BuildScatteredImage(config, logger, image_num, obj_num):
    """
    Build an Image containing multiple objects placed at arbitrary locations.

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`
    @param obj_num             If given, the current `obj_num`

    @returns the final image
    """
    full_xsize = config['image_xsize']
    full_ysize = config['image_ysize']
    wcs = config['wcs']

    full_image = galsim.ImageF(full_xsize, full_ysize)
    full_image.setOrigin(config['image_origin'])
    full_image.wcs = wcs
    full_image.setZero()

    if 'image_pos' in config['image'] and 'world_pos' in config['image']:
        raise AttributeError("Both image_pos and world_pos specified for Scattered image.")

    if 'image_pos' not in config['image'] and 'world_pos' not in config['image']:
        xmin = config['image_origin'].x
        xmax = xmin + full_xsize-1
        ymin = config['image_origin'].y
        ymax = ymin + full_ysize-1
        config['image']['image_pos'] = {
            'type' : 'XY' ,
            'x' : { 'type' : 'Random' , 'min' : xmin , 'max' : xmax },
            'y' : { 'type' : 'Random' , 'min' : ymin , 'max' : ymax }
        }

    if 'nproc' in config['image']:
        nproc = galsim.config.ParseValue(config['image'],'nproc',config,int)[0]
    else:
        nproc = 1

    nobjects = config['nobjects']

    stamps, current_vars = galsim.config.BuildStamps(
            nobjects, config, nproc=nproc, logger=logger, obj_num=obj_num,
            do_noise=False)

    for k in range(nobjects):
        # This is our signal that the object was skipped.
        if not stamps[k].bounds.isDefined(): continue
        bounds = stamps[k].bounds & full_image.bounds
        if False:
            logger.debug('image %d: full bounds = %s',image_num,str(full_image.bounds))
            logger.debug('image %d: stamp %d bounds = %s',image_num,k,str(stamps[k].bounds))
            logger.debug('image %d: Overlap = %s',image_num,str(bounds))
        if bounds.isDefined():
            full_image[bounds] += stamps[k][bounds]
        else:
            if logger and logger.isEnabledFor(logging.INFO):
                logger.warn(
                    "Object centered at (%d,%d) is entirely off the main image,\n"%(
                        stamps[k].bounds.center().x, stamps[k].bounds.center().y) +
                    "whose bounds are (%d,%d,%d,%d)."%(
                        full_image.bounds.xmin, full_image.bounds.xmax,
                        full_image.bounds.ymin, full_image.bounds.ymax))

    current_var = 0
    if 'noise' in config['image']:
        # Bring the image so far up to a flat noise variance
        current_var = FlattenNoiseVariance(config, full_image, stamps, current_vars, logger)
    config['current_var'] = current_var

    return full_image


def AddNoiseScatteredImage(config, logger, image_num, obj_num):
    """
    Add the final noise to a Scattered image

    @param config              A configuration dict.
    @param logger              If given, a logger object to log progress.
    @param image_num           If given, the current `image_num`.
    @param obj_num             If given, the current `obj_num`.
    """
    full_image = config['current_image']
    galsim.config.AddSky(config,full_image)
    if 'noise' in config['image']:
        current_var = config['current_var']
        galsim.config.AddNoise(config,full_image,current_var,logger)


def FlattenNoiseVariance(config, full_image, stamps, current_vars, logger):
    rng = config['rng']
    nobjects = len(stamps)
    max_current_var = max(current_vars)
    if max_current_var > 0:
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug('image %d: maximum noise varance in any stamp is %f',
                         config['image_num'], max_current_var)
        import numpy
        # Then there was whitening applied in the individual stamps.
        # But there could be a different variance in each postage stamp, so the first
        # thing we need to do is bring everything up to a common level.
        noise_image = galsim.ImageF(full_image.bounds)
        for k in range(nobjects):
            b = stamps[k].bounds & full_image.bounds
            if b.isDefined(): noise_image[b] += current_vars[k]
        # Update this, since overlapping postage stamps may have led to a larger
        # value in some pixels.
        max_current_var = numpy.max(noise_image.array)
        if logger and logger.isEnabledFor(logging.DEBUG):
            logger.debug('image %d: maximum noise varance in any pixel is %f',
                         config['image_num'], max_current_var)
        # Figure out how much noise we need to add to each pixel.
        noise_image = max_current_var - noise_image
        # Add it.
        full_image.addNoise(galsim.VariableGaussianNoise(rng,noise_image))
    # Now max_current_var is how much noise is in each pixel.
    return max_current_var


def GetNObjForImage(config, image_num):
    if 'image' in config and 'type' in config['image']:
        image_type = config['image']['type']
    else:
        image_type = 'Single'

    # Check that the type is valid
    if image_type not in valid_image_types:
        raise AttributeError("Invalid image.type=%s."%type)

    nobj_func = eval(valid_image_types[image_type][3])

    return nobj_func(config,image_num)


def GetNObjForSingleImage(config, image_num):
    return 1


def GetNObjForScatteredImage(config, image_num):

    config['index_key'] = 'image_num'
    config['image_num'] = image_num

    # Allow nobjects to be automatic based on input catalog
    if 'nobjects' not in config['image']:
        nobj = galsim.config.ProcessInputNObjects(config)
        if nobj is None:
            raise AttributeError("Attribute nobjects is required for image.type = Scattered")
        return nobj
    else:
        nobj = galsim.config.ParseValue(config['image'],'nobjects',config,int)[0]
        return nobj


def GetNObjForTiledImage(config, image_num):

    config['index_key'] = 'image_num'
    config['image_num'] = image_num

    if 'nx_tiles' not in config['image'] or 'ny_tiles' not in config['image']:
        raise AttributeError(
            "Attributes nx_tiles and ny_tiles are required for image.type = Tiled")
    nx = galsim.config.ParseValue(config['image'],'nx_tiles',config,int)[0]
    ny = galsim.config.ParseValue(config['image'],'ny_tiles',config,int)[0]
    return nx*ny

