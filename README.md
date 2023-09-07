# LogAnalayzer
Script to parse nginx logs and generate report beased on template(report.html).
- nginx log file name format supported: _nginx-*-YYYYMMDD.(gz/log)_   
- only gz and plain logs are accepted
- current nginx format log supported:

  
       log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
                              '$status $body_bytes_sent "$http_referer" '
                              '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '  
                              '$request_time';

  
# How to run

    python log_analayzer.py

optional keys:

--config _'path to config file'_

Default config if conf file is not set:

    [LOG_PARSER]
    "REPORT_SIZE": 1000, # save the number of records by total request time in report
    "REPORT_DIR": "./reports", # path to reports
    "LOG_DIR": "./log", # path to nginx logs
    "APP_LOG": None # path to log file, if 'None' all logs will be written in stdout



