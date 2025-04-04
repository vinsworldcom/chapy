#!/usr/bin/env python3

try:
    from importlib import metadata
except ImportError:
    # Running on pre-3.8 Python; use importlib-metadata package
    import importlib_metadata as metadata
__author__  = 'Michael Vincent <vin@vinsworld.com>'
__date__    = 'Friday September 17, 2021 09:19:04 AM Eastern Daylight Time'
__license__ = 'This software is released under the same terms as Python itself.'
__version__ = metadata.version('chapy')

import os
import sys
import argparse

import docker
import json
import matplotlib.pyplot as plt
import networkx as nx
import subprocess
import threading
import yaml

sys.dont_write_bytecode = True

ENVFILE = ".env"

class _Version(argparse.Action):
    """Print Modules, Python, OS, Program info."""

    def __init__(self, nargs=0, **kw):
        super(_Version, self).__init__(nargs=nargs, **kw)

    def __call__(self, parser, namespace, values, option_string=None):
        print('\nModules, Python, OS, Program info:')
        print('  ' + sys.argv[0])
        print('  Version               ' + __version__)
        print('    argparse            ' + argparse.__version__)
        # Additional modules
        print('    docker              ' + docker.__version__)
        print('    json                ' + json.__version__)
        print('    yaml                ' + yaml.__version__)
        print('    Python version      %s.%s.%s' % sys.version_info[:3])
        print('    Python executable   ' + sys.executable)
        print('    OS                  ' + sys.platform)
        print('\n')
        sys.exit(0)


class ComposeTool(object):

    def __init__(self, args):

        # First defaults
        myenv = {
            'CHAPY_DEFFILE': 'config.json',
            'CHAPY_DOCKYML': 'docker-compose.yml',
            'CHAPY_ALLSERV': "{{ALL}}",
            'CHAPY_HOSTSRV': "{{HOST}}",
            'CHAPY_INDENTS': "4",
            'CHAPY_ISPACER': "=",
            'CHAPY_GPHFONT': "8",
            'CHAPY_GPHNODE': "200",
            'COMPOSE_PROJECT_NAME': ""
        }
        myenv['CHAPY_OUTHEAD'] = myenv['CHAPY_ISPACER'] + "> "

        # Override defaults with .env file
        self._envfile(myenv)
        # Sync local and os.environ, os.environ overrides
        for k in sorted(myenv):
            if k in os.environ:
                myenv[k] = os.environ[k]
            else:
                os.environ[k] = myenv[k]
        # Add any DOCKER_ os.environ to local env
        for k in sorted(os.environ):
            if k.startswith("DOCKER_"):
                myenv[k] = os.environ[k]

        if args.environment:
            print(json.dumps(myenv, sort_keys=True, indent=int(os.environ['CHAPY_INDENTS'])))
            sys.exit(0)

        try:
            client = docker.from_env()
        except docker.errors.DockerException as e:
            print(f"Error contacting Docker for `docker.from_env()`: {e}", file=sys.stderr)
            sys.exit(1)

        args = {}
        if os.environ['COMPOSE_PROJECT_NAME']:
            args = {'name': os.environ['COMPOSE_PROJECT_NAME']}
        self.containers = client.containers.list(filters=args)
        self.env = myenv

    def _envfile(self, output):
        try:
            f = open(ENVFILE, "r")
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                k,v = line.strip('\n').split("=", 1)
                if k not in os.environ:
                    output[k] = os.environ[k] = v
        except FileNotFoundError:
            print(".env file not found", file=sys.stderr)
        return output

    def _list(self, filter=""):
        cs = []
        for c in self.containers:
            if filter == "" or filter in c.name:
                cs.append(c)
        return cs

    def names(self, args):
        names = []
        for c in self.containers:
            if args.filter == "" or args.filter in c.name:
                if args.verbose >= 1:
                    names.append(c.name + "\t[" + c.attrs['Config']['Hostname'] + "]")
                else:
                    names.append(c.name)
        if args.verbose >= 2:
            if not len(self.containers):
                print("no running containers found")
            elif not len(names):
                print(f"no running containers found matching filter: `{args.filter}'")
        return sorted(names)

    def topo(self, args):
        topo = {}
        for c in self.containers:
            if args.filter == "" or args.filter in c.name:
                info = {}

                networks = c.attrs['NetworkSettings']['Networks']
                info['Networks'] = {}
                for n in networks:
                    info['Networks'][n] = networks[n]['IPAddress']

                if args.ports:
                    ports = c.attrs['NetworkSettings']['Ports']
                    info['Ports'] = {}
                    for n in ports:
                        if n in ports and ports[n] is not None:
                            portarray = []
                            for p in ports[n]:
                                portarray.append(f"{p['HostIp']}:{p['HostPort']}")
                            info['Ports'][n] = portarray
                        else:
                            info['Ports'][n] = None

                topo[c.name] = info

        return topo

    def graph(self, args):
        topo = self.topo(args)
        graph = []
        nodes = {}
        nets = {}

        for node in topo.keys():
            nodes[node] = 1
            for net,ip in topo[node]['Networks'].items():
                name = f"NET:{net}"
                nets[name] = 1
                graph.append((node, name, {"IP": ip}))

        G = nx.Graph()
        G.add_edges_from(graph)
        pos = nx.spring_layout(G)
        nx.draw_networkx(G, pos, node_color='green', font_size=int(os.environ['CHAPY_GPHFONT']), with_labels=True,
                         nodelist=list(nodes.keys()), node_shape='o', node_size=int(os.environ['CHAPY_GPHNODE']))
        nx.draw_networkx(G, pos, node_color='grey', font_size=int(os.environ['CHAPY_GPHFONT']), with_labels=True,
                         nodelist=list(nets.keys()), node_shape='s', node_size=int(os.environ['CHAPY_GPHNODE']))
        nx.draw_networkx_edge_labels(G, pos, font_size=(int(os.environ['CHAPY_GPHFONT'])-2))
        plt.show()

    def config(self, args):
        # if os.path.isfile(os.environ['CHAPY_DEFFILE']):
            # print(f"file exists, will not overwrite `{os.environ['CHAPY_DEFFILE']}'", file=sys.stderr)
            # sys.exit(1)
        containers = self.names(args)
        if len(containers) == 0:
            if not os.path.isfile(os.environ['CHAPY_DOCKYML']):
                print(f"no running containers and cannot find `{os.environ['CHAPY_DOCKYML']}'", file=sys.stderr)
                sys.exit(1)

            with open(os.environ['CHAPY_DOCKYML']) as file:
                services = yaml.load(file, Loader=yaml.FullLoader)
            if services is not None and 'services' in services:
                for k in services['services']:
                    containers.append(k)

        config = {}
        for stage in args.stages:
            services = {}
            for c in containers:
                services[c] = []
            config[stage] = services
        return config

    def run(self, args, config):
        self._do_stages(args, config)

    def _do_stages(self, args, config):
        for stage in args.stages:
            if args.verbose >= 2: self._log(f"Stage: {stage}")
            if stage in config:
                self._do_services(args, config[stage])
            else:
                print(f"stage not found: `{stage}'", file=sys.stderr)

    def _do_services(self, args, stage):
        threads = []
        for service in stage:
            filter = service
            if service == os.environ['CHAPY_ALLSERV']:
                filter = ""
            elif args.filter:
                filter = args.filter

            display_service = service
            if args.composev1:
                filter = filter.replace('-', '_')
                display_service = service.replace('-', '_')
            if args.composev2:
                filter = filter.replace('_', '-')
                display_service = service.replace('_', '-')

            if not len(self._list(filter)) and not (service == os.environ['CHAPY_HOSTSRV'] or service == 'localhost'):
                self._log("Service: none matched!", 2)
                return
            if filter in display_service:
                if args.verbose >= 2:
                    if args.filter:
                        self._log(f"Service: {display_service} [Filter = {filter}]", 2)
                    else:
                        self._log(f"Service: {display_service}", 2)
                if args.threads >= 2:
                    x = threading.Thread(target=self._do_hosts, args=(args, stage, service, filter))
                    threads.append(x)
                    x.start()
                else:
                    self._do_hosts(args, stage, service, filter)
        if args.threads >= 2:
            for t in threads:
                t.join()

    def _do_hosts(self, args, stage, service, filter):
        if service == os.environ['CHAPY_HOSTSRV'] or service == 'localhost':
            for cmd in stage[service]:
                if args.verbose >= 2: self._log(f"Command: {cmd}", 6)
                if args.daemon:
                    try:
                        subprocess.Popen(cmd.split(" "))
                    except subprocess.CalledProcessError as e:
                        if args.verbose >= 1: print(e)
                else:
                    try:
                        output = subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT, shell=True)
                        if args.verbose >= 1: print(output.decode('utf8').strip('\n'))
                    except subprocess.CalledProcessError as e:
                        if args.verbose >= 1: print(e.output.decode('utf8').strip('\n'))
        else:
            threads = []
            for c in self._list(filter):
                if args.threads >= 1:
                    x = threading.Thread(target=self._do_commands, args=(args, stage, service, c))
                    threads.append(x)
                    x.start()
                else:
                    self._do_commands(args, stage, service, c)
            if args.threads >= 1:
                for t in threads:
                    t.join()

    def _do_commands(self, args, stage, service, c):
            if args.verbose >= 2: self._log(f"Container: {c.name}", 4)
            for cmd in stage[service]:
                cmd = self._parse_cmd(cmd)
                if args.verbose >= 2: self._log(f"Command: {cmd}", 6)
                if args.dryrun: return
                if args.daemon:
                    output = c.exec_run(cmd, detach=True)
                else:
                    output = c.exec_run(['sh', '-c', cmd])
                    if args.verbose >= 1: print(output.output.decode('utf8').strip('\n'))

    def _parse_cmd(self, cmd):
        for var in os.environ:
            cmd = cmd.replace("{{" + var + "}}", os.environ[var])
        return cmd

    def _log(self, msg, indent=0):
        print(os.environ['CHAPY_ISPACER']*indent + os.environ['CHAPY_OUTHEAD'] + msg)


def main():
    """Main Program."""
    parser = argparse.ArgumentParser(description=
    """
    Compose helper and automtion Python script performs commands in
    container groups according to a staged configuration file or from
    command line input.
    """)
    parser.add_argument('-C', '--config',
        action  = 'store_true',
        help    = "create example config"
    )
    parser.add_argument('-D', '--dryrun',
        action  = 'store_true',
        help    = "show what would be done, do nothing"
    )
    parser.add_argument('-E', '--environment',
        action  = 'store_true',
        help    = "show environment"
    )
    parser.add_argument('-G', '--graph',
        action  = 'store_true',
        help    = "create connectivity graph and exit"
    )
    parser.add_argument('-L', '--list',
        action  = 'store_true',
        help    = "list running container names and exit"
    )
    parser.add_argument('-S', '--list-stages',
        action  = 'store_true',
        help    = "list stages in config file"
    )
    parser.add_argument('-P', '--ports',
        action  = 'store_true',
        help    = "Include ports in topology"
    )
    parser.add_argument('-T', '--topology',
        action  = 'store_true',
        help    = "print running topology (JSON) and exit"
    )
    parser.add_argument('-c1', '--composev1',
        action  = 'store_true',
        help    = "convert '-' to '_' in service names for compose v1"
    )
    parser.add_argument('-c2', '--composev2',
        action  = 'store_true',
        help    = "convert '_' to '-' in service names for compose v2"
    )
    parser.add_argument('-d', '--daemon',
        action  = 'store_true',
        help    = "run commands on containers or host in background"
    )
    parser.add_argument('-f', '--filter',
        type    = str,
        default = "",
        help    = "container name filter"
    )
    parser.add_argument('-s', '--stages',
        type    = str,
        default = "configure,run",
        help    = "comma separated list of config file stages to run"
    )
    parser.add_argument('-t', '--threads',
        action  = 'count',
        default = 0,
        help    = "spawn threads for each container (x1) and service (x2)"
    )
    parser.add_argument('-v', '--verbose',
        action  = 'count',
        default = 0,
        help    = "verbose output (more 'v's = output, status, error)"
    )
    parser.add_argument('-V', '--versions',
        action  = _Version,
        help    = "Print Modules, Python, OS, Program info."
    )
    parser.add_argument('argv',
        nargs   = '*',  # use '*' for optional
        help    = "config file (default: config.json) or command(s)."
    )
    args = parser.parse_args()

    composeTool = ComposeTool(args)

    ### RUN
    args.stages = list(args.stages.split(","))

    if args.list:
        for c in composeTool.names(args):
            print(c)
        sys.exit(0)

    if args.topology or args.ports:
        print(json.dumps(composeTool.topo(args), indent=int(os.environ['CHAPY_INDENTS'])))
        sys.exit(0)

    if args.graph:
        composeTool.graph(args)
        sys.exit(0)

    if args.config:
        print(json.dumps(composeTool.config(args), indent=int(os.environ['CHAPY_INDENTS'])))
        sys.exit(0)

    if args.dryrun:
        args.verbose = 2

    filename = os.environ['CHAPY_DEFFILE']
    if len(args.argv) > 0:
        filename = args.argv[0]
    config = {}

    try:
        file = open(filename, "r")
        try:
            config = json.load(file)
            if args.list_stages:
                for stage in config:
                    print(stage)
                sys.exit(0)

        except json.decoder.JSONDecodeError as e:
            print(f"JSON decode error in `{filename}': {e}", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        if len(args.argv) == 0:
            print(f"No command provided and default file not found: `{filename}'", file=sys.stderr)
            sys.exit(1)
        cmd = []
        svc = {}
        args.stages = ["run"]
        for arg in args.argv:
            cmd.append(arg)
        flt = args.filter
        if args.filter == "":
            flt = os.environ['CHAPY_ALLSERV']
        svc[flt] = cmd
        config[args.stages[0]] = svc

    composeTool.run(args, config)

    return 0


if __name__ == '__main__':
    main()
