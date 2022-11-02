import logging

def get_logger(name, no_log_file=False, stream_level='INFO'):
    """
    setup logger
    """ 
    
    # Setup logging
    LOG = logging.getLogger(name)
    LOG.setLevel(logging.INFO)

    #set format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    #first handler for the file
    #fh = logging.FileHandler('log/app.log', mode='w', encoding='utf-8')
    print(no_log_file)
    if no_log_file == False:
        
        fh = logging.FileHandler('app_logs/app.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        #attach fh handler to LOG
        LOG.addHandler(fh)

    #second handler for screen
    sh = logging.StreamHandler()
    if stream_level == 'DEBUG':
        sh.setLevel(logging.DEBUG)
    else:
        sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)

    #attach sh handler to LOG
    LOG.addHandler(sh)

    # Avoid propagation to root logger (to avoid double print on screen)
    LOG.propagate = False

    return LOG