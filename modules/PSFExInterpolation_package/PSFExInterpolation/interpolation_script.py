import numpy as np
import psfex
import scatalog as sc
import re
from astropy.io import fits

class PSFExInterpolator(object):
    def __init__(self, dotpsf_path, galcat_path, output_path):
        self._dotpsf_path = dotpsf_path # Path to PSFEx output file
        self._galcat_path = galcat_path # Path to catalog containing galaxy positions
        self._output_path = output_path+'galaxy_psf'   # Path to output file to be written
        self._pos_params = None
        self.gal_pos = None
        self.interp_PSFs = None
        
        # get number naming convention for this particular run
        s=re.split("\-([0-9]{3})\-([0-9]+)\.",self._galcat_path)
        self._img_number='-{0}-{1}'.format(s[1],s[2])      
        
    def _get_position_parameters(self):
        self._pos_params = ['XWIN_IMAGE', 'YWIN_IMAGE'] #TEMP: hardcoded pos params
        
    def _get_galaxy_positions(self):
        if self._pos_params is None:
            self._get_position_parameters()
        
        galcat = sc.FITSCatalog(self._galcat_path, SEx_catalog=True)
        galcat.open()
        gal_data = galcat.get_data()
        self.gal_pos = np.array([[x,y] for x,y in zip(gal_data[self._pos_params[0]],
                                 gal_data[self._pos_params[1]])])
        galcat.close()
    
    def _interpolate(self):
        if self.gal_pos is None:
            self._get_galaxy_positions()
        
        pex = psfex.PSFEx(self._dotpsf_path)
        self.interp_PSFs = np.array([pex.get_rec(x,y) for x,y in zip(self.gal_pos[:,0],
                                     self.gal_pos[:,1])])
        
    def write_output(self):
        if self.interp_PSFs is None:
            self._interpolate()
        output = fits.ImageHDU(self.interp_PSFs)
        output.writeto(self._output_path+self._img_number+'.fits', overwrite=True)
