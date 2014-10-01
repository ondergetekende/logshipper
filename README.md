
Log shipper
===================

Introduction
---

`logshipper`  is a tool to gather logs from various sources, process them and send them elsewhere. It is similar to [logstash](https://logstash.net), except it doesn't use the java virtual machine and ruby class library, which should help improve performance and decrease memory hunger.


Key concepts
---
**Pipelines** are lists of steps to be performed on a log message. Pipelines are stored in `yaml` format.  Common tasks are to drop irrelevant messages, extract valuable data and sending the message somewhere.

**Steps** are part of pipelines. They typically contain a `match` action to apply the task only to specific messages. Tasks can contain multiple actions.

**Actions** are part of steps. Actions include `match`, `set` and `statsd`. An action receives the message, and can alter it, send it somewhere, ignore it, or decide this action should be skipped.

Actions
---
###match
The match action matches a regex to a specific field of a message. Only when all of the regexes matches, the rest of the actions of this step will get executed.

Named groups get registered as variables, which can be accessed in subsequent steps. When there's a single match, unnamed groups get registered as backreferences, and are avail during the rest of the step. 

Example:

    match:
        message: (start_time):\s+(?P<time>\d+)
    set: 
        start_time: "{1} {time}"
      
A shorter syntax is available when there's a single match against the `message` field, the above example is equivalent to:

    match: (start_time):\s+(?P<time>\d+)
    set: 
        start_time: "{1} {time}"
     
###set

Sets fields of the message. For an example, see `match`

###rabbitmq

Sends messages to RabbitMQ. Accepts the following parameters:

* **username** RabbitMQ username, defaults to `guest`
* **password** RabbitMQ password, defaults to `guest`
* **host** RabbitMQ hostname, defaults to `127.0.0.1`
* **port** RabbitMQ port, defaults to `5672`
* **exchange** Defaults to `logshipper`
* **queue** Defaults to `logshipper`
* **key** The routing key. Defaults to `logshipper`

###statsd
Sends a value to statsd.

* **host** defaults to `127.0.0.1`
* **port** defaults to `8125`
* **sample_rate** defaults to `1.0`
* **type** Accepted values are `counter`, `gauge` and `timer`, defaults to `counter`
* **value** The value to send. Defaults to `1.0`
* **multiplier** The amount to multiply the value by. Defaults to `1.0`
* **delta** boolean, only used for gauge, whether to send differential values or absolute values. Defaults to `False`
* **prefix** the prefix for the stat name backreferences not allowed
* **name** the name for the stat, backreferences allowed (required)

### drop
Drops the message.

