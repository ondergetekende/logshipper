[<img src="https://img.shields.io/travis/ondergetekende/logshipper.svg?style=flat">](https://travis-ci.org/ondergetekende/logshipper)
[<img src="https://img.shields.io/coveralls/ondergetekende/logshipper.svg?style=flat">](https://coveralls.io/r/ondergetekende/logshipper)
[<img src="https://img.shields.io/pypi/v/logshipper.svg?style=flat">](https://pypi.python.org/pypi/logshipper)
[<img src="https://img.shields.io/pypi/dm/logshipper.svg?style=flat">](https://pypi.python.org/pypi/logshipper)
[<img src="https://pypip.in/py_versions/logshipper/badge.svg?style=flat">](https://pypi.python.org/pypi/logshipper)
[<img src="https://img.shields.io/pypi/l/logshipper.svg?style=flat">](https://github.com/ondergetekende/logshipper/blob/master/LICENSE)
[<img src="(https://img.shields.io/scrutinizer/g/ondergetekende/logshipper.svg?style=flat">]https://scrutinizer-ci.com/g/ondergetekende/logshipper/)


Log shipper
===================

Introduction
---

`logshipper`  is a tool to gather logs from various sources, process them and send them elsewhere. It is similar to [logstash](https://logstash.net), except it doesn't use the java virtual machine and ruby class library, which should help improve performance and decrease memory hunger.

In logshipper, logmessages travel to pipelines. Pipelines may have their own sources of logs, called inputs, or they may be invoked by other pipelines. In the pipeline, the log message travels through a number of steps. Each of those steps may modify the message, send it elsewhere or ignore it altogether.

Example:
---

```yaml
inputs:
- tail: 
    filename: /var/log/messages
steps:
- match: "myapps\.test"
  extract: "widget=(\d+)"
  set:
    widget: {1}

- elasticsearch:
    url: http://127.0.0.1:9200
```

In this example pipeline, all meessages appended to `/var/log/syslog` are sent to elasticsearch. When a message contains the text `myapps.test`, the strings like `widget=172` are parsed into a separate field.

Key concepts
---
**Pipelines** are lists of steps to be performed on a log message. Common tasks are to drop irrelevant messages, extract valuable data and sending the message somewhere. Pipelines contain zero or more *inputs*, and a number of steps. 

**Steps** are part of pipelines. They consist of one one or more *actions*, which act on a log message. A typical step consist of a match action, and either a manipulator action, or an output action, although all of those are optional.

**Actions** are part of steps. Actions fall into one of three categories: match action, manipulator actions, and output actions, although this distinction is not very strict.