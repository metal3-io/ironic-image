=============================
Middlewares and configuration
=============================

Middlewares can be configured in multiple fashion depending of the
application needs. Here is some use-cases: 

Configuration from the application
----------------------------------

The application code will looks like::

    from oslo_middleware import sizelimit
    from oslo_config import cfg

    conf = cfg.ConfigOpts()
    app = sizelimit.RequestBodySizeLimiter(your_wsgi_application, conf)


Configuration with paste-deploy and the oslo.config
---------------------------------------------------

The paste filter (in /etc/my_app/api-paste.ini) will looks like::

    [filter:sizelimit]
    use = egg:oslo.middleware#sizelimit
    # In case of the application doesn't use the global oslo.config 
    # object. The middleware must known the app name to load 
    # the application configuration, by setting this:
    #  oslo_config_project = my_app

    # In some cases, you may need to specify the program name for the project
    # as well.
    #  oslo_config_program = my_app-api

The oslo.config file of the application (eg: /etc/my_app/my_app.conf) will looks like::

    [oslo_middleware]
    max_request_body_size=1000


Configuration with pastedeploy only
-----------------------------------

The paste filter (in /etc/my_app/api-paste.ini) will looks like::

    [filter:sizelimit]
    use = egg:oslo.middleware#sizelimit
    max_request_body_size=1000

This will override any configuration done via oslo.config


.. note::

    healtcheck middleware does not yet use oslo.config, see :doc:`../reference/healthcheck_plugins`

