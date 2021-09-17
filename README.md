# Docker Compose Helper and Automation Tool

A Python tool for interfacing with Docker and Docker Compose environments.

## Dependencies

[Docker SDK for Python](https://pypi.org/project/docker/)

## Installation

    sudo python3 -mpip install .

## Usage

The `cha.py` tool will look for `.env` in the current directory to get the 
`COMPOSE_PROJECT_NAME` environment variable to be able to better filter on 
containers related to the specific Docker Compose project environment.

Environment variables can be set to control the operation of `cha.py`.  The 
environment variables can be overriden in the `.env` file.  To see the 
effective environment variables for the current project, use the 
`--environment` option.

The `cha.py` tool will look for `CHAPY_DEFFILE` (config.json) in the current 
directory to find the commands to run.  If a configuration file is not 
specified on the command line and the `CHAPY_DEFFILE` file is not found in the 
current directory, `cha.py` assumes the command line arguments are commands to 
run.  If no commands are specified on the command line, the program exists 
with error.

The example `config.json` file shows the structure:

```
{
  "configure": {
    "service_name_1": [
      "pwd",
      "ls"
    ]
  },
  "run": {},
  "custom_stage": {
    "{{ALL}}": [
      "head -1 /etc/hosts"
    ]
  }
}
```

The top level specifies "stages".  The default stages are:
  - configure
  - run

The `--stages` command line option narrows which stages to run if desired.

The "run" stage above is provided as it is "requried" by default, but there 
are no tasks to execute in this case.

Custom stages are created simply by defining them.  They will not run unless 
specified with the `--stages` command line option.

The next level defines "services" from the Docker Compose file.  These are 
used as filters to the Docker API to narrow which containers the commands run 
on.  For example, in the "configure" stage, only containers matching the name 
\*service_name_1\* will be operated on.  If all containers are desired, use 
the `CHAPY_ALLSERV` services keyword as shown above.  Configured services can be 
overridden on the command line with the `--filter` option.  If the command 
is to be run on the container host rather than in any of the containers, use 
the `CHAPY_HOSTSRV` services keyword.

Within each "services" object is a list of commands to run.  To substitue 
variables in the config file with environment variables on the host machine, 
enclose the variable name in double braces `{{VAR_NAME}}`.  For example:

```
echo {{COMPOSE_PROJECT_NAME}}
```

will print the compose project name in the container based on the value of 
`COMPOSE_PROJECT_NAME` assigned in the '.env' file or the local host's 
environment variables.

By default, no output is shown.  To see output from the commands, use one `-v` 
command line option.

## Examples

Get a list of the containers found in the current Docker Compose context:

`cha.py --list`

Narrow the list to containers whose name contains "net":

`cha.py --list --filter net`

Run the "configure" and "run" stages in the local directory's `config.json` 
file:

`cha.py`

Same, but this time see the commands' output:

`cha.py -v`

Run one-off commands on all containers:

`cha.py -v hostname "cat /etc/hostname"`

Now use a different configuration file:

`cha.py configs/myconfig.json`

And now run just the custom stage "poststart" on containers whose name matches 
\*network\* and see the output:

`cha.py -v configs/myconfig.json --stage poststart --filter network`

See **everything**:

`cha.py -vvv configs/myconfig.json`
