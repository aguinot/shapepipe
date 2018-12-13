#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Module cfis.py

CFIS module

:Authors: Martin Kilbinger

:Date: 19/01/2018
"""

# Compability with python2.x for x>6
from __future__ import print_function


import re
import sys
import os
import glob

import numpy as np

from astropy import units
from astropy.io import ascii
from astropy.coordinates import Angle
from astropy.coordinates import SkyCoord

from generic import stuff


unitdef = 'degree'

# Maybe define class for these constants?
size = {}
size['tile']     = 0.5
size['weight']   = 0.5
size['exposure'] = 1.0

# Cut criteria for exposures
exp_time_min     = 95
flag_valid       = 'V'


class image():

    def __init__(self, name, ra, dec, exp_time=-1, valid='Unknown'):
        """Create image information.

        Parameters
        ----------
        name: string
            file name
        ra: Angle
            right ascension
        dec: Angle
            declination
        exp_time: integer, optiona, default=-1
            exposure time
        valid: string, optional, default='Unknown'
            validation flag

        Returns
        -------
        self: class image
            image information
        """
            
        self.name     = name
        self.ra       = ra
        self.dec      = dec
        if exp_time == None:
            self.exp_time = -1
        else:
            self.exp_time = exp_time
        if valid == None:
            self.valid = 'Unknown'
        else:
            self.valid = valid


    def cut(self, no_cuts=False):
        """Return True (False) if image does (not) need to be cut from selection.

        Parameters
        ----------
        no_cuts: bool, optiona, default=False
            do not cut if True

        Returns
        -------
        cut: bool
            True (False) if image is (not) cut
        """

        # Do not cut if no_cuts flag is set
        if no_cuts == True:
            return False

        # Cut if exposure time smaller than minimum (and not flagged as unknown or n/a)
        if self.exp_time < exp_time_min and self.exp_time != -1:
            return True

        # Cut if validation flag is not valid (and not unknown)
        if self.valid != flag_valid and self.valid != 'Unknown':
            return True

        return False


    def print(self, file=sys.stdout):
        """Print image information as ascii Table column

        Parameters
        ----------
        file: file handle, optional, default=sys.stdout
            output file handle

        Returns
        -------
        None
        """

        print('{} {:10.2f} {:10.2f} {:5d} {:8s}'.format(self.name, getattr(self.ra, unitdef), getattr(self.dec, unitdef), \
              self.exp_time, self.valid), file=file)


    def print_header(self, file=sys.stdout):
        """Print header for ascii Table output

        Parameters
        ----------
        file: file handle, optional, default=sys.stdout
            output file handle

        Returns
        -------
        None
        """

        print('#Name ra[{0}] dec[{0}] exp_time[s] validation'.format(unitdef), file=file)



def get_file_pattern(pattern, band, image_type, want_re=True):
    """Return file pattern of CFIS image file.
    """

    if pattern == '':
        if image_type in ('exposure', 'exposure_flag', 'exposure_flag.fz', \
		'exposure_weight', 'exposure_weight.fz'):
            pattern_base = '\d{7}p'
        else:
            pattern_base  = 'CFIS.*\.{}'.format(band)
    else:
        pattern_base = pattern


    if image_type == 'exposure':
        pattern  = '{}\.fits.fz'.format(pattern_base)

    elif image_type == 'exposure_flag':
        pattern  = '{}\.flag.fits'.format(pattern_base)

    elif image_type == 'exposure_flag.fz':
        pattern  = '{}\.flag.fits.fz'.format(pattern_base)

    elif image_type == 'exposure_weight':
        pattern  = '{}\.weight.fits'.format(pattern_base)

    elif image_type == 'exposure_weight.fz':
        pattern  = '{}\.weight.fits.fz'.format(pattern_base)

    elif image_type == 'tile':
        pattern = '{}\.fits'.format(pattern_base)

    elif image_type == 'cat':
        pattern = '{}\.cat'.format(pattern_base)

    elif image_type == 'weight':
        pattern = '{}\.weight\.fits'.format(pattern_base)

    elif image_type == 'weight.fz':
        pattern = '{}\.weight\.fits.fz'.format(pattern_base)

    else:
        stuff.error('Invalid type \'{}\''.format(image_type))

    if want_re == False:
        pattern = pattern.replace('\\', '')

    return pattern


def get_tile_number_from_coord(ra, dec, return_type=str):
    """Return CFIS stacked image tile number covering input coordinates.
        This is the inverse to get_tile_coord_from_nixy.

    Parameters
    ----------
    ra: Angle
        right ascension
    dec: Angle
        declination
    return type: <type 'type'>
	return type, int or str

    Returns
    -------
    nix: string
        tile number for x
    niy: string
        tile number for y
    """

    y = (dec.degree + 90) * 2.0
    yi = int(np.rint(y))

    x = ra.degree * np.cos(dec.radian) * 2.0
    #x = ra.degree * 2 * np.cos(y/2 / 180 * np.pi - np.pi/2)
    xi = int(np.rint(x))
    if xi == 720:
        xi = 0

    if return_type == str:
        nix = '{:03d}'.format(xi)
        niy = '{:03d}'.format(yi)
    elif return_type == int:
        nix = xi
        niy = yi
    else:
        stuff.error('Invalid return type {}'.format(return_type))

    return nix, niy


def get_tile_coord_from_nixy(nix, niy):
    """ Return coordinates corresponding to tile with number (nix,niy).
        This is the inverse to get_tile_number_from_coord.
    Parameters
    ----------
    nix: string
        tile number for x
    niy: string
        tile number for y

    Returns
    -------
    ra: Angle
        right ascension
    dec: Angle
        declination
    """

    xi = int(nix)
    yi = int(niy)

    d = (yi/2.0 - 90)
    dec = Angle('{} degrees'.format(d))
    r = xi / 2.0 / np.cos(dec.radian)
    ra = Angle('{} degrees'.format(r))

    return ra, dec



def get_tile_name(nix, niy, band):
    """Return tile name for given tile numbers.

   Parameters
   ----------
    nix: string
        tile number for x
    niy: string
        tile number for y
    band: string
        band, one in 'r' or 'u'

    Returns
    -------
    tile_name: string
        tile name
    """

    if type(nix) is int and type(niy) is int:
    	tile_name = 'CFIS.{:03d}.{:03d}.{}.fits'.format(nix, niy, band)

    elif type(nix) is str and type(niy) is str:
    	tile_name = 'CFIS.{}.{}.{}.fits'.format(nix, niy, band)

    else:
        stuff.error('Invalid type for input tile numbers {}, {}'.format(nix, niy))


    return tile_name



def get_tile_number(tile_name):
    """Return tile number of given image tile name

    Parameters
    ----------
    tile_name: string
        tile name

    Returns
    -------
    nix: string
        tile number for x
    niy: string
        tile number for y
    """

    m = re.search('CFIS\.(\d{3})\.(\d{3})', tile_name)
    if m == None or len(m.groups()) != 2:
        stuff.error('Image name \'{}\' does not match tile name syntax'.format(tile_name))

    nix = m.groups()[0]
    niy = m.groups()[1]

    return nix, niy



def get_log_file(path, verbose=False):
    """Return log file content

    Parameters
    ----------
    path: string
        log file path
    verbose: bool, optional, default=False
        verbose output if True

    Returns
    -------
    log: list of strings
        log file lines
    """

    if not os.path.isfile(path):
        stuff.error('Log file \'{}\' not found'.format(path))

    f_log = open(path, 'r')
    log   = f_log.readlines()
    if verbose:
        print('Reading log file, {} lines found'.format(len(log)))
    f_log.close()

    return log



def check_ra(ra):
    """Range check of right ascension.

    Parameters
    ----------
    ra: Angle
        right ascension

    Returns
    -------
    res: bool
        result of check (True if pass, False if fail)
    """

    print(ra.deg)
    if ra.deg < 0 or ra.deg > 360:
        stuff.error('Invalid ra, valid range is 0 < ra < 360 deg')
        return 1

    return 0



def check_dec(dec):
    """Range check of declination.

    Parameters
    ----------
    dec: Angle
        declination

    Returns
    -------
    res: bool
        result of check (True if pass, False if fail)
    """

    if dec.deg < -90 or dec.deg > 90:
        stuff.error('Invalid dec, valid range is -90 < dec < 90 deg')
        return 1

    return 0



def get_Angle(str_coord):
    """Return Angles ra, dec from coordinate string

    Parameters
    ----------
    str_coord: string
        string of input coordinates

    Returns
    -------
    ra: Angle
        right ascension
    dec: Angle
        declination
    """

    ra, dec = stuff.my_string_split(str_coord, num=2, stop=True)

    a_ra  = Angle(ra)
    a_dec = Angle(dec)

    return r_ra, a_dec



def get_Angle_arr(str_coord, num=-1, verbose=False):
    """Return array of Angles from coordinate string

    Parameters
    ----------
    str_coord: string
        string of input coordinates
    num: int, optional, default=-1
        expected number of coordinates (even number)
    verbose: bool, optional, default=False
        verbose output

    Returns
    -------
    angles: array of SkyCoord
        array of sky coordinates (pairs ra, dec)
    """

    angles_mixed = stuff.my_string_split(str_coord, num=num, verbose=verbose, stop=True)
    n = len(angles_mixed)
    n = int(n / 2)

    angles = []
    for i in range(n):
        c = SkyCoord(angles_mixed[2*i], angles_mixed[2*i+1])
        angles.append(c)

    return angles



def read_list(fname, col=None):
    """Read list from ascii file.

    Parameters
    ----------
    fname: string
        ascii file name
    col: string, optional, default=None
        column name

    Returns
    -------
    file_list: list of strings
        list of file name
    """

    if col is None:
        f = open(fname, 'rU')
        file_list = [x.strip() for x in f.readlines()]
        f.close()
    else:
        import pandas as pd
        dat = pd.read_csv(fname, sep='\s+')
        file_list = dat[col].values

    # from sapastro1:toolbox/python/CFIS.py
    #except IOError as exc:
        #if exc.errno == errno.ENOENT:
            #if verbose == True:
                #print('Not using exclude file')
            #out_list = []
        #else:
            #raise


    file_list.sort()
    return file_list


def create_image_list(fname, ra, dec, exp_time=[], valid=[]):
    """Return list of image information.

    Parameters
    ----------
    fname: list of strings
        file names
    ra: list of strings
        right ascension
    dec: list of strings
        declination
    exp_time: list of integers, optional, default=[]
        exposure time
    valid: list of strings, optional, default=[]
        QSO exposure validation flag

    Returns
    -------
    images: list of cfis.image
        list of image information
    """

    nf = len(fname)
    nr = len(ra)
    nd = len(dec)
    if nf == 0:
        stuff.error('No entries in file name list')
    if (nf != nr or nf != nd) and nr != 0 and nd != 0:
        stuff.error('Lists fname, ra, dec have not same length ({}, {}, {})'.format(nf, nr, nd))

    images = []
    for i in range(nf):
        if nr > 0 and nd > 0:
            r = Angle('{} {}'.format(ra[i], unitdef))
            d = Angle('{} {}'.format(dec[i], unitdef))
        else:
            r = None
            d = None
        if len(exp_time) > 0:
            e = exp_time[i]
        else:
            e = -1
        if len(valid) > 0:
            v = valid[i]
        else:
            v = None
        im = image(fname[i], r, d, exp_time=e, valid=v)
        images.append(im)

    return images


def get_exposure_info(logfile_name, verbose=False):  
    """Return information on run (single exposure) from log file.

    Parameters
    ----------
    logfile_name: string
        file name
    verbose: bool, optional, default=False
        verbose output

    Returns:
    images: list of class image
        list of exposures
    """

    images = []
    f = open(logfile_name)
    for line in f:
        dat = re.split(' |', line)
        name = dat[0]
        ra   = Angle(' hours'.format(dat[8]))
        dec  = Angle(' degree'.format(dat[9]))
        valid = dat[21]
    
        img = image(name, ra, dec, valid=valid)
        image.append(img)

    return image



def get_image_list(inp, band, image_type, col=None, verbose=False):
    """Return list of images.

    Parameters
    ----------
    inp: string
        file name or direcory path
    band: string
        optical band
    image_type: string
        image type ('tile', 'exposure', 'cat', 'weight', 'weight.fz')
    col: string, optionalm default=None
        column name for file list input file
    verbose: bool, optional, default=False
        verbose output if True

    Return
    ------
    img_list: list of class cfis.image
        image list
    """

    file_list     = []
    ra_list       = []
    dec_list      = []
    exp_time_list = []
    valid_list    = []

    if os.path.isdir(inp):
        if col is not None:
            stuff.error('Column name only valid if input is file')

        # Read file names from directory listing
        inp_type  = 'dir'
        file_list = glob.glob('{}/*'.format(inp))

    elif os.path.isfile(inp):
        if image_type in ('tile', 'weight', 'weight.fz'):
            # File names in single-column ascii file
            inp_type  = 'file'
            file_list = read_list(inp, col=col)
        elif image_type == 'exposure':
            # File names and coordinates in ascii file
            inp_type  = 'file'
            dat = ascii.read(inp)

            if len(dat.keys()) == 3:
                # File is exposure + coord list (obtained from get_coord_CFIS_pointings.py)
                file_list = dat['Pointing']
                ra_list   = dat['R.A.[degree]']
                dec_list  = dat['Declination[degree]']
            elif len(dat.keys()) == 12:
                # File is log file, e.g. from http://www.cfht.hawaii.edu/Science/CFIS-DATA/logs/MCLOG-CFIS.r.qso-elx.log
                # Default file separator is '|'
                for d in dat:
                    file_list.append('d{}p.fits.fz'.format(d['col1']))
                    ra  = re.split('\s*', d['col4'])[0]
                    dec = re.split('\s*', d['col4'])[1]
                    ra_list.append(Angle('{} hours'.format(ra)).degree)
                    dec_list.append(dec)
                    exp_time = int(d['col5'])
                    exp_time_list.append(exp_time)
                    valid = re.split('\s*', d['col11'])[2]
                    valid_list.append(valid)
            else:
                stuff.error('Wrong file format, #columns={}, has to be 3 or 12'.format(len(dat.keys())))
        else:
            stuff.error('Image type \'{}\' not supported'.format(image_type))

    # Create list of objects, coordinate lists can be empty
    image_list = create_image_list(file_list, ra_list, dec_list, exp_time=exp_time_list, valid=valid_list)

    # Filter file list to match CFIS image pattern
    img_list = []
    pattern = get_file_pattern('', band, image_type)

    for img in image_list:

        m = re.findall(pattern, img.name)
        if len(m) != 0:
            img_list.append(img)

    if verbose == True and len(img_list) > 0:
        print('{} image files found in input {} \'{}\''.format(len(img_list), inp_type, inp))

    return img_list



def exclude(f, exclude_list):
    """Return True if f is on exclude_list

    Parameters
    ----------
    f: string
        file name
    exclude_list: list of strings
        list of files

    Returns
    -------
    is_in_exclude: bool
        True (False) if f is in list
    """

    return f in exclude_list


def log_append_to_tiles_exp(log, exp_path, tile_num, k_img, k_weight, k_flag, exp_num):
    """Append information to tiles-exposure log string lines
    """

    log.append('{}  {}   {} {} {}  {}\n'.format(exp_path, tile_num, k_img, k_weight, k_flag, exp_num))

    return log



def log_line_get_entry(log_line, entry):
    """Return entry from log string line
    """

    line_s = log_line.split()

    if entry == 'exp_name':
        return line_s[0]
    elif entry == 'tile_num':
        return line_s[1]
    elif entry == 'exp_num':
        return line_s[5]
    else:
        stuff.error('Entry \'{}\' not valid in tiles-expsure log string'.format(entry))



def log_get_exp_nums_for_tiles_num(log, tile_num):
    """Return all exposure numbers for a given tile number
    """

    exp_num = []

    for line in log:
        my_tile_num = log_line_get_entry(line, 'tile_num')
        if tile_num == my_tile_num:
            exp_num.append(log_line_get_entry(line, 'exp_num'))

    if len(exp_num) == 0:
        stuff.error('Tile number \'{}\' not found in log file'.format(tile_num))

    return exp_num



def log_get_exp_names_for_tiles_num(log, tile_num):
    """Return all exposure file names for a given tile number
    """

    exp_names = []

    for line in log:
        my_tile_num = log_line_get_entry(line, 'tile_num')
        if tile_num == my_tile_num:
            exp_names.append(log_line_get_entry(line, 'exp_name'))

    if len(exp_names) == 0:
        stuff.error('Tile number \'{}\' not found in log file'.format(tile_num))

    return exp_names



def log_get_tile_nums(log):
    """Return all tile numbers from log file.

    Parameters
    ----------
    log: list of strings
        log file content

    Returns
    -------
    tile_nums: list of strings
        list of tile numbers
    """

    tile_nums = []
    for line in log:
        my_tile_num = log_line_get_entry(line, 'tile_num')
        tile_nums.append(my_tile_num)

    return set(tile_nums)


