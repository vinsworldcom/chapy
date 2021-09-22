from setuptools import setup

setup(
    name             = 'chapy',
    version          = '1.1',
    description      = 'Docker Compose Helper and Automation Tool.',
    url              = 'https://github.com/vinsworldcom/chapy.git',
    author           = 'Michael Vincent',
    author_email     = 'vin@vinsworld.com',
    packages         = [
    ],
    install_requires = [
        'importlib-metadata ~= 1.0 ; python_version < "3.8"',
        'docker',
        'pyyaml'
    ],
    scripts          = [
        'bin/cha.py'
    ],
    zip_safe         = False
)
