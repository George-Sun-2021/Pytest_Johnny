#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import base64
import os
import pytest
import allure
import logging
from py.xml import html

from config import constants
from config.conf import cm
from common.readconfig import ini
from Utils.times import timestamp
from Utils.send_mail import send_report

from selenium import webdriver
from selenium.webdriver import Remote
from selenium.webdriver.chrome.options import Options as CO
from selenium.webdriver.firefox.options import Options as FO
from selenium.webdriver.ie.options import Options as IEO

driver = None


def pytest_addoption(parser):
    """
    定义钩子函数hook进行命令行定义浏览器传参，默认chrome,定义浏览器启动方式传参，默认启动
    @param parser:
    @return:
    """
    # 浏览器选项
    parser.addoption(
        "--br",
        action="store",
        dest="browser",
        type=str.lower,
        default=constants.Browser.GOOGLE_CHROME,
        choices=constants.ValidBrowsers.valid_browsers,
        help="""Specifies the web browser to use. Default: Chrome.
                If you want to use Firefox, explicitly indicate that.
                Example: (--br=firefox)""")

    # 是否开启浏览器界面选项
    parser.addoption(
        "--is_headless",
        action="store",
        dest="headless",
        default=False,
        help="""Using this makes Webdriver run web browsers
                headlessly, which is required on headless machines.
                Default: False on Mac/Windows. True on Linux.""",
    )

    parser.addoption(
        "--test_env",
        action="store",
        dest="env",
        choices=(
            constants.Environment.DEVLOCAL,
            constants.Environment.DEVINT,
            constants.Environment.BVT_DTTL,
            constants.Environment.BVT_KPMG,
            constants.Environment.BVT_BDO,
            constants.Environment.BVT_RSM,
        ),
        default=constants.Environment.DEVLOCAL,
        help="""Specifies the test enviroment to use. Default: dev local.
                If you want to choose other envrioments, explicitly indicate that.
                Example: (--test_env=devInt)""",
    )


@pytest.fixture(scope='session', autouse=True)
def drivers(request):
    global driver
    browser = request.config.getoption("browser")
    # headless or not
    headless = request.config.getoption("headless")
    print("获取命令行传参：{}".format(request.config.getoption("browser")))
    if not headless:
        if browser == "chrome":
            driver = webdriver.Chrome()
        elif browser == "firefox":
            driver = webdriver.Firefox()
        elif browser == "ie":
            driver = webdriver.Ie()
        else:
            logging.info("发送错误浏览器参数：{}".format(browser))
    else:
        if browser == "chrome":
            chrome_options = CO()
            chrome_options.add_argument('--headless')
            driver = webdriver.Chrome(chrome_options=chrome_options)
        elif browser == "firefox":
            firefox_options = FO()
            firefox_options.add_argument('--headless')
            driver = webdriver.Firefox(firefox_options=firefox_options)
        elif browser == "ie":
            ie_options = IEO()
            ie_options.add_argument('--headless')
            driver = webdriver.Ie(ie_options=ie_options)
        else:
            logging.info("发送错误浏览器参数：{}".format(browser))

    driver.maximize_window()
    yield driver
    # driver.close()
    driver.quit()
    # return driver


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    """
    当测试失败的时候，自动截图，展示到html报告中
    :param item:
    """
    pytest_html = item.config.pluginmanager.getplugin('html')
    outcome = yield
    report = outcome.get_result()
    report.description = str(item.function.__doc__)
    extra = getattr(report, 'extra', [])

    if report.when == 'call' or report.when == "setup":
        xfail = hasattr(report, 'wasxfail')
        if (report.skipped and xfail) or (report.failed and not xfail):
            screen_img = _capture_screenshot()
            if screen_img:
                html = '<div><img src="data:image/png;base64,%s" alt="screenshot" style="width:1024px;height:768px;" ' \
                       'onclick="window.open(this.src)" align="right"/></div>' % screen_img
                extra.append(pytest_html.extras.html(html))
        report.extra = extra


def pytest_html_results_table_header(cells):
    cells.insert(1, html.th('用例名称'))
    cells.insert(2, html.th('Test_nodeid'))
    cells.pop(2)


def pytest_html_results_table_row(report, cells):
    cells.insert(1, html.td(report.description))
    cells.insert(2, html.td(report.nodeid))
    cells.pop(2)


def pytest_html_results_table_html(report, data):
    if report.passed:
        del data[:]
        data.append(html.div('通过的用例未捕获日志输出.', class_='empty log'))


# def pytest_html_report_title(report):
#     report.title = "pytest示例项目测试报告"


def pytest_configure(config):
    config._metadata.clear()
    config._metadata['测试项目'] = "测试百度官网搜索"
    config._metadata['测试地址'] = ini.url


def pytest_html_results_summary(prefix, summary, postfix):
    # prefix.clear() # 清空summary中的内容
    prefix.extend([html.p("所属部门: XX公司测试部")])
    prefix.extend([html.p("测试执行人: 随风挥手")])


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """收集测试结果"""
    result = {
        "total": terminalreporter._numcollected,
        'passed': len(terminalreporter.stats.get('passed', [])),
        'failed': len(terminalreporter.stats.get('failed', [])),
        'error': len(terminalreporter.stats.get('error', [])),
        'skipped': len(terminalreporter.stats.get('skipped', [])),
        # terminalreporter._sessionstarttime 会话开始时间
        'total times': timestamp() - terminalreporter._sessionstarttime
    }
    print(result)
    if result['failed'] or result['error']:
        send_report()


def _capture_screenshot():
    """截图保存为base64"""
    now_time, screen_file = cm.screen_path
    driver.save_screenshot(screen_file)
    allure.attach.file(screen_file,
                       "失败截图{}".format(now_time),
                       allure.attachment_type.PNG)
    with open(screen_file, 'rb') as f:
        imagebase64 = base64.b64encode(f.read())
    return imagebase64.decode()
