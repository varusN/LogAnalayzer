#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import configparser
import gzip
import logging
import os
import re
import statistics as s
import sys
import time
from string import Template

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "APP_LOG": None,
    "parser_errors_threshold": 0.1,
}

lineformat = re.compile(
    r"""(?P<remote_addr>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) (?P<remote_user>.+)  (?P<http_x_real_ip>.+) \[(?P<time_local>\d{2}\/[a-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} (\+|\-)\d{4})\] ["](?P<method>.+) (?P<url>.+) (?P<proto>.+)["] (?P<status>\d{3}) (?P<body_bytes_sent>\d+) (["](?P<http_referer>(\-)|(.+))["]) (["](?P<http_user_agent>.+)["]) (["](?P<http_x_forwarded_for>(\-)|(.+))["]) (["](?P<http_X_REQUEST_ID>.+)["]) (["](?P<http_X_RB_USER>.+)["]) (?P<request_time>.+)""",
    re.IGNORECASE,
)

urls = dict()
parsed_records = 0
total_time = 0
start_time = time.time()
exit_flag = False


class UrlColection:
    # url: str
    # requests_time: list
    def __init__(self, url, request_time):
        self.url = url
        self.requests_time = [request_time]

    def add_item(self, request_time):
        self.requests_time.append(request_time)

    def count(self):
        return len(self.requests_time)

    def count_perc(self, parsed_records):
        return round((self.count() / parsed_records) * 100, 3)

    def time_sum(self):
        return round(sum(self.requests_time), 3)

    def time_perc(self, total_time):
        return round((self.time_sum() / total_time) * 100, 3)

    def time_avg(self):
        return round(s.mean(self.requests_time), 3)

    def time_max(self):
        return round(max(self.requests_time), 3)

    def time_med(self):
        return round(s.median(self.requests_time), 3)


def main():
    # parsing incoming args
    parser = argParser()
    conf_file = vars(parser.parse_args(sys.argv[1:]))

    # generating active config and logger
    if conf_file:
        exit_flag, log_dir, report_dir, report_size, app_log = get_config(
            conf_file["config"]
        )
    logger = init_logger(app_log)
    logger.info(
        f"Start with config: REPORT_SIZE: {report_size}, \
            REPORT_DIR: {report_dir}, \
            LOG_DIR: {log_dir}, \
            APP_LOG: {app_log}"
    )
    if exit_flag:
        sys.exit()
    # searching log file
    try:
        exit_flag, report_date, log_file = get_log_file(logger, log_dir, report_dir)
    except OSError:
        logger.exception("Fatal Error on getting log file")
        exit_flag = True
    if exit_flag:
        sys.exit()
    # gathering log data
    log_data, log_records = read_log_file(logger, log_dir, log_file)
    for line in log_data:
        log_parser(line)
    # check total not parsed lines
    exit_flag = check_parser_errors(
        logger, log_records, log_file, config["parser_errors_threshold"]
    )
    if exit_flag:
        sys.exit()

    # calculate stat and build report
    stat = get_stat(urls, report_size)
    exit_flag = build_report(logger, report_dir, stat, report_date, log_records)
    if exit_flag:
        sys.exit()


def init_logger(app_log):
    logging.basicConfig(
        level=logging.INFO,
        filename=app_log,
        filemode="w",
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def argParser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="./conf.ini", type=str)
    return parser


def get_config(conf_file):
    exit_flag = False
    conf = configparser.ConfigParser()
    try:
        with open(conf_file) as f:
            conf.read_string(f.read())
    except OSError:
        print(f"File {conf_file} does not exist or can't be read")
        exit_flag = True
        return exit_flag, None, None, None, None
    for line in config:
        try:
            config[line] = conf["LOG_PARSER"][line]
        except:
            pass
    log_dir = config["LOG_DIR"]
    report_dir = config["REPORT_DIR"]
    report_size = int(config["REPORT_SIZE"])
    app_log = config["APP_LOG"]
    return exit_flag, log_dir, report_dir, report_size, app_log


def get_log_file(logger, log_dir, report_dir):
    exit_flag = False
    files = dict()
    for file in os.listdir(log_dir):
        basename, extension = get_name_extention(file)
        log_date = re.findall(r"nginx.+(?P<date>\d{8})", basename)
        if log_date:
            files[file] = int(log_date[0])
    if len(log_date) == 0:
        logger.error("There are no nginx logs, exit")
        exit_flag = True
        return exit_flag, None, None
    file_date = max(files.values())
    exit_flag, report_date = check_report(logger, report_dir, file_date)
    if exit_flag:
        return exit_flag, None, None
    log = {k: v for k, v in files.items() if v == file_date}
    log_file = list(log.keys())[0]
    exit_flag = check_extention(logger, log_file)
    if exit_flag:
        return exit_flag, None, None
    logger.info(f"New log file found: {log_file}")
    return exit_flag, report_date, log_file


def read_log_file(logger, log_dir, log_file):
    operator = (open, gzip.open)[log_file.endswith(".gz")]
    try:
        with operator(os.path.join(log_dir, log_file), "rb") as f:
            data = f.readlines()
    except OSError:
        logger.exception(f"Logfile {log_file} open error")
    return data, len(data)


def log_parser(line):
    global parsed_records, total_time, urls
    if isinstance(line, str):
        line = re.search(lineformat, line)
    elif isinstance(line, bytes):
        line = re.search(lineformat, line.decode("utf-8"))
    if line:
        datadict = line.groupdict()
        link = datadict["url"]
        request_time = float(datadict["request_time"])
        if link != "" and request_time != "":
            if link in urls.keys():
                url = urls[link]
                url.add_item(request_time)
            else:
                url = UrlColection(url=link, request_time=request_time)
                urls[link] = url
            parsed_records += 1
            total_time += request_time


def get_stat(urls, report_size):
    stat = []
    for line in urls.keys():
        url_stat = dict()
        url_stat["url"] = line
        url_stat["count"] = urls[line].count()
        url_stat["count_perc"] = urls[line].count_perc(parsed_records)
        url_stat["time_sum"] = urls[line].time_sum()
        url_stat["time_perc"] = urls[line].time_perc(total_time)
        url_stat["time_avg"] = urls[line].time_avg()
        url_stat["time_max"] = urls[line].time_max()
        url_stat["time_med"] = urls[line].time_med()
        stat.append(url_stat)
    stat.sort(key=lambda dictionary: dictionary["time_sum"], reverse=True)
    stat = stat[:report_size]
    return stat


def check_parser_errors(logger, log_records, log_file, parser_errors):
    exit_flag = False
    if log_records == 0:
        logger.error(f"Empty file {log_file}, exit")
        exit_flag = True
    elif 1 - parsed_records / log_records > parser_errors:
        logger.error(f"Too many errors incorrect lines in log file {log_file}, exit")
        exit_flag = True
    return exit_flag


def check_report(logger, report_dir, log_date):
    """Check if report already created and return date in report format"""
    exit_flag = False
    report_date = time.strftime("%Y.%m.%d", time.strptime(str(log_date), "%Y%m%d"))
    for file in os.listdir(report_dir):
        data = re.findall(f"report-{report_date}.html", file)
        if data:
            logger.error("There are no new nginx log files to work on, exit")
            exit_flag = True, None
    return exit_flag, report_date


def check_extention(logger, file):
    exit_flag = False
    basename, extension = get_name_extention(file)
    if extension not in (".gz", ".log"):
        logger.error(
            f"Incorrect extension in file {file}, .gz and .log are supported only, exit"
        )
        exit_flag = True
    return exit_flag


def get_name_extention(file):
    basename, extension = os.path.splitext(file)
    return basename, extension


def build_report(logger, report_dir, stat, report_date, log_records):
    try:
        with open("report.html") as f:
            template = f.read()
    except OSError:
        logger.exception("Error while open report template(report.html)")
    result = Template(template).safe_substitute(table_json=stat)
    try:
        with open(os.path.join(report_dir, f"report-{report_date}.html"), "w+") as f:
            f.write(result)
    except OSError:
        logger.exception("Error while saving new report")
    logger.info(
        f"New report-{report_date}.html created for {round(time.time() - start_time, 3)}\
         seconds. Parsed records: {parsed_records}, overal log recors: {log_records}."
    )


if __name__ == "__main__":
    main()
