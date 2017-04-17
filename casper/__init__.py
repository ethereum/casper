# -*- coding: utf-8 -*-
# ############# version ##################
import os.path
import re
import subprocess

from pkg_resources import get_distribution, DistributionNotFound

GIT_DESCRIBE_RE = re.compile('^(?P<version>v\d+\.\d+\.\d+)-(?P<git>\d+-g[a-fA-F0-9]+(?:-dirty)?)$')


__version__ = None
try:
    _dist = get_distribution('casper')
    # Normalize case for Windows systems
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, 'casper')):
        # not installed, but there is another version that *is*
        raise DistributionNotFound
    __version__ = _dist.version
except DistributionNotFound:
    pass

if not __version__:
    try:
        rev = subprocess.check_output(['git', 'describe', '--tags', '--dirty'],
                                      stderr=subprocess.STDOUT)
        match = GIT_DESCRIBE_RE.match(rev)
        if match:
            __version__ = "{}+git-{}".format(match.group("version"), match.group("git"))
    except:
        pass

if not __version__:
    __version__ = 'undefined'

# ########### endversion ##################
