import http.server
import json
import logging
import os
import platform
import subprocess
import urllib.parse

from modules.configuration import load_configuration, save_configuration
from modules.json import json_load
from modules.server.auxiliary import refresh, get_value, save_progress
from modules.server.status_server import StatusServer
from modules.server.run import run_windows, run_linux
from modules.structures.review import Review

configuration = load_configuration()
INPUT_PGN_FILE = configuration['paths']['input_pgn']
LOG_FILE = configuration['paths']['log']

logger = logging.getLogger('handler')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())

DEFAULT_ERROR_MESSAGE = """
<!DOCTYPE HTML>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Error response</title>
        <link href="/css/style.css" rel="stylesheet">
    </head>
    <body>
        <h1>Error response</h1>
        <p>Error code: %(code)d</p>
        <p>Message: %(message)s.</p>
        <p>Error code explanation: %(code)s - %(explain)s.</p>
        <footer>
            <a href="https://github.com/JakimPL/Chess-Tactic-Finder/">Tactic Finder by Jakim (2023).</a>
        </footer>
    </body>
</html>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    status_server: StatusServer

    def __init__(self, request, client_address, server, **kwargs):
        self.error_message_format = DEFAULT_ERROR_MESSAGE
        super().__init__(request, client_address, server, **kwargs)

    def send_text(self, text: str):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Content-Length', str(text))
        self.end_headers()
        self.wfile.write(bytes(text, 'utf-8'))

    def send_json(self, dictionary: dict):
        json_string = json.dumps(dictionary)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Content-Length', str(len(json_string)))
        self.end_headers()
        self.wfile.write(bytes(json_string, 'utf-8'))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == '/refresh':
            parameters = dict(urllib.parse.parse_qsl(parsed_url.query))
            gather_games = parameters.get('gather', 'false') == 'true'
            refresh(self.log_message, gather_games=gather_games)
            text = 'Refreshed.'
            self.log_message(text)
            self.send_text(text)
        elif parsed_url.path == '/analysis_state':
            message = Handler.status_server.message
            dictionary = dict(urllib.parse.parse_qsl(message))
            self.send_json(dictionary)
        elif parsed_url.path == '/reinstall':
            self.log_message('Reinstalling...')
            if platform.system() == 'Windows':
                result = subprocess.run(
                    [os.path.join('shell', 'bat', 'install.bat')],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            elif platform.system() == 'Linux':
                path = os.path.join('shell', 'sh', 'install.sh')
                run_windows(path)
                result = subprocess.run(
                    [os.path.join('shell', 'sh', 'install.sh')],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                raise NotImplementedError(f'Platform {platform.system()} is not supported')

            result = result.stdout.decode()
            self.send_text(result)
        elif parsed_url.path.endswith(('.py', '.pyc', '.bat', '.sh', '.tactic', '.vars', '.md', '.txt')):
            self.send_error(404)
        elif 'save' in parsed_url.path:
            puzzle_id, value = parsed_url.path.split('/')[-2:]
            value = get_value(value)
            result = str(save_progress(self.log_message, puzzle_id, value))
            self.send_text(result)
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == '/analyze':
            self.analyze('analyze')
        elif parsed_url.path == '/review':
            self.analyze('review')
        elif parsed_url.path == '/get_chart':
            length = int(self.headers['Content-Length'])
            path = self.rfile.read(length).decode('utf-8')
            dictionary = json_load(path)
            review = Review.from_json(dictionary)
            graph_data = review.plot_evaluations()
            self.send_text(graph_data)
        elif parsed_url.path == '/save_configuration':
            self.log_message('Saving configuration...')
            length = int(self.headers['Content-Length'])
            config = json.loads(self.rfile.read(length).decode('utf-8'))
            save_configuration(config)
            result = 'Configuration saved.'
            self.send_text(result)

    def list_directory(self, path):
        self.send_error(404)

    def analyze(self, mode: str):
        self.log_message('Analyzing...')
        length = int(self.headers['Content-Length'])
        pgn = self.rfile.read(length).decode('utf-8')

        with open(INPUT_PGN_FILE, 'w') as file:
            file.write(pgn)

        if platform.system() == 'Windows':
            path = os.path.join('shell', 'bat', 'analyze.bat')
            command = f'{path} {mode}.py {INPUT_PGN_FILE}'
            run_windows(command)

        elif platform.system() == 'Linux':
            path = os.path.join('shell', 'sh', 'analyze.sh')
            command = f'{path} {mode}.py {INPUT_PGN_FILE}'
            run_linux(command)
            
        else:
            raise NotImplementedError(f'Platform {platform.system()} is not supported')

        result = 'Analysis started.'
        # result = 'result: Analysis started \n'
        # path = f'path: {path} \n'
        # mode = f'mode: {mode} \n'
        # pgn_input = f'PGN: {INPUT_PGN_FILE} \n'
        self.send_text(result)
        # self.send_text(path)
        # self.send_text(mode)
        # self.send_text(INPUT_PGN_FILE)

    def log_message(self, format, *args):
        message = format % args
        logger.info(
            "%s - - [%s] %s" % (
                self.address_string(),
                self.log_date_time_string(),
                message
            )
        )
