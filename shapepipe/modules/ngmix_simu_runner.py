# -*- coding: utf-8 -*-

""" NGMIX RUNNER

This file contains methods to run ngmix for shape measurement.

:Author: Axel Guinot

"""

from shapepipe.modules.module_decorator import module_runner
from shapepipe.pipeline import file_io as io
from sqlitedict import SqliteDict

import re

import numpy as np
from numpy.random import uniform as urand

import ngmix
from ngmix.observation import Observation, ObsList, MultiBandObsList
from ngmix.fitting import LMSimple

import galsim


def get_prior():
    """ Get prior

    Return prior for the different parameters

    Return
    ------
    prior : ngmix.priors
        Priors for the different parameters.

    """

    # prior on ellipticity.  The details don't matter, as long
    # as it regularizes the fit.  This one is from Bernstein & Armstrong 2014
    g_sigma = 0.4
    g_prior = ngmix.priors.GPriorBA(g_sigma)

    # 2-d gaussian prior on the center
    # row and column center (relative to the center of the jacobian, which would be zero)
    # and the sigma of the gaussians
    # units same as jacobian, probably arcsec
    row, col = 0.0, 0.0
    row_sigma, col_sigma = 0.186, 0.186  # pixel size of DES
    cen_prior = ngmix.priors.CenPrior(row, col, row_sigma, col_sigma)

    # T prior.  This one is flat, but another uninformative you might
    # try is the two-sided error function (TwoSidedErf)
    Tminval = -10.0  # arcsec squared
    Tmaxval = 1.e6
    T_prior = ngmix.priors.FlatPrior(Tminval, Tmaxval)

    # similar for flux.  Make sure the bounds make sense for
    # your images
    Fminval = -1.e4
    Fmaxval = 1.e9
    F_prior = ngmix.priors.FlatPrior(Fminval, Fmaxval)

    # now make a joint prior.  This one takes priors
    # for each parameter separately
    prior = ngmix.joint_prior.PriorSimpleSep(cen_prior,
                                             g_prior,
                                             T_prior,
                                             F_prior)

    return prior


def local_wcs(wcs, x_pos, y_pos):
    """
    """

    g_wcs = galsim.fitswcs.AstropyWCS(wcs=wcs)
    image_pos = galsim.PositionD(x=x_pos, y=y_pos)

    return g_wcs.local(image_pos)


def get_jacob(wcs, x_pos, y_pos):
    """ Get jacobian

    Return the jacobian of the wcs at the required position.

    Parameters
    ----------
    wcs : astropy.wcs.WCS
        WCS object for wich we want the jacobian.
    ra : float
        Ra position of the center of the vignet (in Deg).
    dec : float
        Dec position of the center of the vignet (in Deg).

    Returns
    -------
    galsim_jacob : galsim.wcs.BaseWCS.jacobian
        Jacobian of the WCS at the required position.

    """

    g_wcs = galsim.fitswcs.AstropyWCS(wcs=wcs)
    # world_pos = galsim.CelestialCoord(ra=ra*galsim.angle.degrees,
    #                                   dec=dec*galsim.angle.degrees)
    image_pos = galsim.PositionD(x=x_pos, y=y_pos)
    galsim_jacob = g_wcs.jacobian(image_pos)

    return galsim_jacob


# def do_ngmix_metacal(gals, psfs, psfs_sigma, weights, flags, jacob_list, prior):
#     """ Do ngmix metacal

#     Do the metacalibration on a multi-epoch object and return the join shape
#     measurement with ngmix

#     Parameters
#     ---------
#     gals : list
#         List of the galaxy vignets.
#     psfs : list
#         List of the PSF vignets.
#     psfs_sigma : list
#         List of the sigma PSFs.
#     weights : list
#         List of the weight vignets.
#     flags : list
#         List of the flag vignets.
#     jacob_list : list
#         List of the jacobians.
#     prior : ngmix.priors
#         Priors for the fitting parameters.

#     Returns
#     -------
#     metacal_res : dict
#         Dictionary containing the results of ngmix metacal.

#     """

#     n_epoch = len(gals)
#     # n_epoch = 1

#     psf_pars = {'maxfev': 5000,
#                'xtol': 5.0e-6,
#                'ftol': 5.0e-6}

#     if n_epoch == 0:
#         raise ValueError("0 epoch to process")

#     # Make observation
#     gal_obs_list = ObsList()
#     T_guess_psf = []
#     psf_res_gT = {'g_PSFo': np.array([0., 0.]), 
#                   'g_err_PSFo': np.array([0., 0.]),
#                   'T_PSFo': 0.,
#                   'T_err_PSFo': 0.}
#     wsum = 0.
#     for n_e in range(n_epoch):

#         w = np.copy(weights[n_e])
#         w[np.where(flags[n_e] != 0)] = 0.

#         psf_jacob = ngmix.Jacobian(row=(psfs[0].shape[0]-1)/2., col=(psfs[0].shape[1]-1)/2., wcs=jacob_list[n_e])
#         # psf_jacob = ngmix.DiagonalJacobian(row=(psfs[0].shape[0]-1)/2., col=(psfs[0].shape[1]-1)/2., scale=0.187)

#         gal_jacob = ngmix.Jacobian(row=(gals[0].shape[0]-1)/2., col=(gals[0].shape[1]-1)/2., wcs=jacob_list[n_e])
#         # gal_jacob  = ngmix.DiagonalJacobian(row=gals[0].shape[0]/2., col=gals[0].shape[1]/2., scale=0.187)
        
#         # psf_jacob = None
#         # gal_jacob = None

#         psf_obs = Observation(psfs[n_e], jacobian=psf_jacob)

#         psf_T = 2. * psfs_sigma[n_e]**2.

#         boot_psf = ngmix.bootstrap.PSFRunner(psf_obs, 'gauss', psf_T, psf_pars)

#         boot_psf.go(ntry=2)

#         psf_res = boot_psf.fitter.get_result()

#         w_tmp = np.sum(w)

#         if psf_res['flags'] == 0:
#             psf_obs.set_gmix(boot_psf.fitter.get_gmix())
#             psf_res_gT['g_PSFo'] += psf_res['g']*w_tmp 
#             psf_res_gT['g_err_PSFo'] += np.array([psf_res['pars_err'][2], psf_res['pars_err'][3]])*w_tmp
#             psf_res_gT['T_PSFo'] += psf_res['T']*w_tmp
#             psf_res_gT['T_err_PSFo'] += psf_res['T_err']*w_tmp
#             wsum += w_tmp
#         else:
#             raise Exception('Fit PSF failed !')

#         # pfitter = ngmix.fitting.LMSimple(psf_obs, 'gauss')
#         # pfitter.go([0., 0., 0., 0., psf_T, 1*0.186**2.])
#         # psf_obs.set_gmix(pfitter.get_gmix())

#         gal_obs = Observation(gals[n_e], weight=w, jacobian=gal_jacob, psf=psf_obs)

#         gal_obs_list.append(gal_obs)
#         T_guess_psf.append(psf_T)

#     for key in psf_res_gT.keys():
#         psf_res_gT[key] /= wsum

#     boot = ngmix.bootstrap.MaxMetacalBootstrapper(gal_obs_list)
#     psf_model = 'gauss'
#     gal_model = 'gauss'

#     # metacal specific parameters
#     metacal_pars = {'types': ['noshear', '1p', '1m', '2p', '2m'],
#                     'psf': 'fitgauss',
#                     'fixnoise': True,
#                     'cheatnoise': False,
#                     'symmetrize_psf': False}

#     # maximum likelihood fitter parameters
#     # parameters for the Levenberg-Marquardt fitter in scipy
#     lm_pars = {'maxfev': 2000,
#                'xtol': 5.0e-6,
#                'ftol': 5.0e-6}
#     max_pars = {
#         # use scipy.leastsq for the fitting
#         'method': 'lm',

#         # parameters for leastsq
#         'lm_pars': lm_pars}

#     # psf_pars = {'maxiter': 5000,
#     #             'tol': 5.0e-6}
#     psf_pars = {'maxfev': 5000,
#                'xtol': 5.0e-6,
#                'ftol': 5.0e-6}

#     # Tguess = np.mean(T_guess_psf)*0.186**2  # size guess in arcsec
#     Tguess = np.mean(T_guess_psf)
#     # Tguess = 4.
#     # Tguess = 4.0*0.186**2
#     ntry = 10       # retry the fit twice
#     boot.fit_metacal(psf_model,
#                      gal_model,
#                      max_pars,
#                      Tguess,
#                      prior=prior,
#                      ntry=ntry,
#                      metacal_pars=metacal_pars,
#                      psf_fit_pars=psf_pars,
#                      psf_ntry=5,
#                      use_galsim=True)


#     # result dictionary, keyed by the types in metacal_pars above
#     metacal_res = boot.get_metacal_result()
#     print(metacal_res['noshear']['T'])
#     metacal_res.update(psf_res_gT)

#     return metacal_res

    
def do_ngmix_metacal(gals, psfs, psfs_sigma, weights, flags, jacob_list, prior):
    """ Do ngmix metacal

    Do the metacalibration on a multi-epoch object and return the join shape
    measurement with ngmix

    Parameters
    ---------
    gals : list
        List of the galaxy vignets.
    psfs : list
        List of the PSF vignets.
    psfs_sigma : list
        List of the sigma PSFs.
    weights : list
        List of the weight vignets.
    flags : list
        List of the flag vignets.
    jacob_list : list
        List of the jacobians.
    prior : ngmix.priors
        Priors for the fitting parameters.

    Returns
    -------
    metacal_res : dict
        Dictionary containing the results of ngmix metacal.

    """

    n_epoch = len(gals)
    # n_epoch = 1

    psf_pars = {'maxfev': 5000,
               'xtol': 5.0e-6,
               'ftol': 5.0e-6}

    if n_epoch == 0:
        raise ValueError("0 epoch to process")

    # Make observation
    gal_obs_list = ObsList()
    T_guess_psf = []
    psf_res_gT = {'g_PSFo': np.array([0., 0.]), 
                  'g_err_PSFo': np.array([0., 0.]),
                  'T_PSFo': 0.,
                  'T_err_PSFo': 0.}
    wsum = 0.
    for n_e in range(n_epoch):

        w = np.copy(weights[n_e])
        w[np.where(flags[n_e] != 0)] = 0.

        psf_jacob = ngmix.Jacobian(row=(psfs[0].shape[0]-1)/2., col=(psfs[0].shape[1]-1)/2., wcs=jacob_list[n_e])
        # psf_jacob = ngmix.DiagonalJacobian(row=(psfs[0].shape[0]-1)/2., col=(psfs[0].shape[1]-1)/2., scale=0.187)

        gal_jacob = ngmix.Jacobian(row=(gals[0].shape[0]-1)/2., col=(gals[0].shape[1]-1)/2., wcs=jacob_list[n_e])
        # gal_jacob  = ngmix.DiagonalJacobian(row=gals[0].shape[0]/2., col=gals[0].shape[1]/2., scale=0.187)
        
        # psf_jacob = None
        # gal_jacob = None

        psf_obs = Observation(psfs[n_e], jacobian=psf_jacob)

        psf_T = 2. * psfs_sigma[n_e]**2.

        boot_psf = ngmix.bootstrap.PSFRunner(psf_obs, 'gauss', psf_T, psf_pars)

        boot_psf.go(ntry=2)

        psf_res = boot_psf.fitter.get_result()

        w_tmp = np.sum(w)

        if psf_res['flags'] == 0:
            psf_obs.set_gmix(boot_psf.fitter.get_gmix())
            psf_res_gT['g_PSFo'] += psf_res['g']*w_tmp 
            psf_res_gT['g_err_PSFo'] += np.array([psf_res['pars_err'][2], psf_res['pars_err'][3]])*w_tmp
            psf_res_gT['T_PSFo'] += psf_res['T']*w_tmp
            psf_res_gT['T_err_PSFo'] += psf_res['T_err']*w_tmp
            wsum += w_tmp
        else:
            raise Exception('Fit PSF failed !')

        # pfitter = ngmix.fitting.LMSimple(psf_obs, 'gauss')
        # pfitter.go([0., 0., 0., 0., psf_T, 1*0.186**2.])
        # psf_obs.set_gmix(pfitter.get_gmix())

        gal_obs = Observation(gals[n_e], weight=w, jacobian=gal_jacob, psf=psf_obs)

        gal_obs_list.append(gal_obs)
        T_guess_psf.append(psf_T)

    for key in psf_res_gT.keys():
        psf_res_gT[key] /= wsum

    psf_model = 'gauss'
    gal_model = 'gauss'

    # metacal specific parameters
    metacal_pars = {'types': ['noshear', '1p', '1m', '2p', '2m'],
                    'step': 0.01,
                    'psf': 'fitgauss',
                    'fixnoise': True,
                    'cheatnoise': False,
                    'symmetrize_psf': False}

    # maximum likelihood fitter parameters
    # parameters for the Levenberg-Marquardt fitter in scipy
    lm_pars = {'maxfev': 2000,
               'xtol': 5.0e-5,
               'ftol': 5.0e-5}
    max_pars = {
        # use scipy.leastsq for the fitting
        'method': 'lm',

        # parameters for leastsq
        'lm_pars': lm_pars}

    # psf_pars = {'maxiter': 5000,
    #             'tol': 5.0e-6}
    psf_pars = {'maxfev': 5000,
               'xtol': 5.0e-6,
               'ftol': 5.0e-6}

    # Tguess = np.mean(T_guess_psf)*0.186**2  # size guess in arcsec
    Tguess = np.mean(T_guess_psf)
    # Tguess = 4.
    # Tguess = 4.0*0.186**2

    obs_dict_mcal = ngmix.metacal.get_all_metacal(gal_obs_list, **metacal_pars)
    res = {'mcal_flags': 0}
    ntry=2
    for key in sorted(obs_dict_mcal):

        try:
            ss = galsim.hsm.FindAdaptiveMom(galsim.Image(obs_dict_mcal[key][0].image, scale=0.187), strict=False)
            guess_flux = ss.moments_amp
            guess_size = 2.*(ss.moments_sigma*0.187)**2.
            guess_centroid = ss.moments_centroid
            gal_pars = [(guess_centroid.x-26)*0.187,
                        (guess_centroid.y-26)*0.187,
                        0., 0.,
                        guess_size,
                        guess_flux]
        except:
            gal_pars = [0., 0., 0., 0., 1, 100]

        guess = np.copy(gal_pars)
        for ii in range(ntry):
            guess[0:5] += urand(low=-0.1,high=0.1)
            guess[5:] *= (1.0 + urand(low=-0.1, high=0.1))
            try:
                # fitter1 = ngmix.galsimfit.LMSimple(obs_dict_mcal[key], gal_model)
                # fitter1.go(guess)
                # fres1 = fitter1.get_result()
                
                fitter = ngmix.galsimfit.GalsimSimple(obs_dict_mcal[key], gal_model)
                fitter.go(guess)
                fres = fitter.get_result()
            except:
                continue

            if fres['flags'] == 0:
                break
        # except Exception as err:
        #     print(err)
        #     fres = {'flags': np.ones(1, dtype=[('flags', 'i4')])}

        # print("ntry : {}".format(ii))
        
        res['mcal_flags'] |= fres['flags']
        tres = {}

        for name in fres.keys():
            tres[name] = fres[name]
        tres['flags'] = fres['flags']

        boot = ngmix.bootstrap.Bootstrapper(obs_dict_mcal[key])
        boot.fit_psfs(psf_model, Tguess, ntry=5,
                      fit_pars=psf_pars, skip_already_done=False)

        wsum     = 0.0
        Tpsf_sum = 0.0
        gpsf_sum = np.zeros(2)
        npsf=0
        for obslist in boot.mb_obs_list:
            for obs in obslist:
                if hasattr(obs,'psf_nopix'):
                    #print("    summing nopix")
                    g1,g2,T=obs.psf_nopix.gmix.get_g1g2T()
                else:
                    g1,g2,T=obs.psf.gmix.get_g1g2T()

                # TODO we sometimes use other weights
                twsum = obs.weight.sum()

                wsum += twsum
                gpsf_sum[0] += g1*twsum
                gpsf_sum[1] += g2*twsum
                Tpsf_sum += T*twsum
                npsf+=1

        tres['gpsf'] = gpsf_sum/wsum
        tres['Tpsf'] = Tpsf_sum/wsum

        res[key] = tres

    # result dictionary, keyed by the types in metacal_pars above
    metacal_res = res
    # print("T : {}      {}".format(metacal_res['noshear']['T'], fres1['T']))
    # print("Tgal/Tpsf : {:.2f}      {:.2f}".format(res['noshear']['T']/res['noshear']['Tpsf'], fres1['T']/res['noshear']['Tpsf']))
    # print("Flux : {}      {}".format(metacal_res['noshear']['flux'], fres1['flux']/0.187**2.))
    # print("s2n : {}      {}".format(res['noshear']['s2n_r'], fres1['s2n']))
    metacal_res.update(psf_res_gT)

    return metacal_res



# def do_ngmix(gals, psfs, psfs_sigma, weights, flags, jacob_list, prior):
#     """ Do ngmix metacal

#     Do the metacalibration on a multi-epoch object and return the join shape
#     measurement with ngmix

#     Parameters
#     ---------
#     gals : list
#         List of the galaxy vignets.
#     psfs : list
#         List of the PSF vignets.
#     psfs_sigma : list
#         List of the sigma PSFs.
#     weights : list
#         List of the weight vignets.
#     flags : list
#         List of the flag vignets.
#     jacob_list : list
#         List of the jacobians.
#     prior : ngmix.priors
#         Priors for the fitting parameters.

#     Returns
#     -------
#     metacal_res : dict
#         Dictionary containing the results of ngmix metacal.

#     """

#     # n_epoch = len(gals)
#     n_epoch = 1

#     if n_epoch == 0:
#         raise ValueError("0 epoch to process")

#     # Make observation
#     gal_obs_list = ObsList()
#     T_guess_psf = []
#     for n_e in range(n_epoch):

#         # psf_jacob = ngmix.Jacobian(row=psfs[0].shape[0]/2., col=psfs[0].shape[1]/2., wcs=jacob_list[n_e])
#         # gal_jacob = ngmix.Jacobian(row=gals[0].shape[0]/2., col=gals[0].shape[1]/2., wcs=jacob_list[n_e])
#         psf_jacob = None
#         gal_jacob = None

#         psf_obs = Observation(psfs[n_e], jacobian=psf_jacob)

#         psf_T = 2. * psfs_sigma[n_e]**2.

#         w = np.copy(weights[n_e])
#         w[np.where(flags[n_e] != 0)] = 0.

#         gal_obs = Observation(gals[n_e], weight=w, jacobian=gal_jacob, psf=psf_obs)

#         gal_obs_list.append(gal_obs)
#         T_guess_psf.append(psf_T)

#     boot = ngmix.bootstrap.Bootstrapper(gal_obs_list)
#     psf_model = 'gauss'
#     gal_model = 'gauss'

#     # maximum likelihood fitter parameters
#     # parameters for the Levenberg-Marquardt fitter in scipy
#     lm_pars = {'maxfev': 2000,
#                'xtol': 5.0e-5,
#                'ftol': 5.0e-5}
#     max_pars = {
#         # use scipy.leastsq for the fitting
#         'method': 'lm',

#         # parameters for leastsq
#         'lm_pars': lm_pars}

#     # psf_pars = {'maxiter': 5000,
#     #             'tol': 5.0e-6}
#     psf_pars = {'maxfev': 2000,
#                'xtol': 5.0e-5,
#                'ftol': 5.0e-5}

#     # Tguess = np.mean(T_guess_psf)*0.186**2  # size guess in arcsec
#     Tguess = np.mean(T_guess_psf)
#     # Tguess = 4.
#     # Tguess = 4.0*0.186**2
#     ntry = 2       # retry the fit twice

#     boot.fit_psfs(psf_model, Tguess, ntry=20, fit_pars=psf_pars, skip_already_done=False)

#     boot.fit_max(gal_model, max_pars, prior=prior, ntry=2)

#     boot.set_round_s2n()

#     tres = boot.get_max_fitter().get_result()
#     rres = boot.get_round_result()

#     tres['s2n_r'] = rres['s2n_r']
#     tres['T_r'] = rres['T_r']
#     tres['psf_T_r'] = rres['psf_T_r']

#     ngmix_res = {'mcal_flags':0}
#     ngmix_res['mcal_flags'] |= tres['flags']
#     ngmix_res['mcal_flags'] |= rres['flags']


#     wsum = 0.
#     Tpsf_sum = 0.
#     gpsf_sum = np.zeros(2)
#     npsf = 0
#     for obslist in boot.mb_obs_list:
#         for obs in obslist:
#             if hasattr(obs, 'psf_nopix'):
#                 g1,g2,T = obs.psf_nopix.gmix.get_g1g2T()
#             else:
#                 g1,g2,T = obs.psf.gmix.get_g1g2T()

#             twsum = obs.weight.sum()

#             wsum += twsum
#             gpsf_sum[0] += g1*twsum
#             gpsf_sum[1] += g2*twsum
#             Tpsf_sum += T*twsum
#             npsf+=1

#     tres['gspf'] = gpsf_sum/wsum
#     tres['Tpsf'] = Tpsf_sum/wsum

#     ngmix_res['noshear'] = tres

#     return ngmix_res


def compile_results(results):
    """ Compile results

    Prepare the results of ngmix before saving.

    Parameters
    ----------
    results : dict
        Dictionary containing the results of ngmix metacal.

    Returns
    -------
    output_dict : dict
        Dictionary containing ready to be saved.

    """

    names = ['1m', '1p', '2m', '2p', 'noshear']
    names2 = ['id', 'n_epoch_model',
              'psf_true_e1', 'psf_true_e2', 'psf_true_sigma',
              'psf_true_e1m', 'psf_true_e2m', 'psf_true_sigmam',
              'g1_psfo_ngmix', 'g2_psfo_ngmix', 'T_psfo_ngmix',
              'g1_err_psfo_ngmix', 'g2_err_psfo_ngmix', 'T_err_psfo_ngmix',
              'g1', 'g1_err', 'g2', 'g2_err', 
              'T', 'T_err', 'Tpsf', 
              's2n', 
              'flags', 'mcal_flags']
    output_dict = {k: {kk: [] for kk in names2} for k in names}
    for i in range(len(results)):
        for name in names:
            output_dict[name]['id'].append(results[i]['obj_id'])
            output_dict[name]['n_epoch_model'].append(results[i]['n_epoch_model'])
            output_dict[name]['psf_true_e1'].append(results[i]['psf_true_e1'])
            output_dict[name]['psf_true_e2'].append(results[i]['psf_true_e2'])
            output_dict[name]['psf_true_sigma'].append(results[i]['psf_true_sigma'])
            output_dict[name]['psf_true_e1m'].append(np.mean(results[i]['psf_true_e1']))
            output_dict[name]['psf_true_e2m'].append(np.mean(results[i]['psf_true_e2']))
            output_dict[name]['psf_true_sigmam'].append(np.mean(results[i]['psf_true_sigma']))
            output_dict[name]['g1_psfo_ngmix'].append(results[i]['g_PSFo'][0])
            output_dict[name]['g2_psfo_ngmix'].append(results[i]['g_PSFo'][1])
            output_dict[name]['g1_err_psfo_ngmix'].append(results[i]['g_err_PSFo'][0])
            output_dict[name]['g2_err_psfo_ngmix'].append(results[i]['g_err_PSFo'][1])
            output_dict[name]['T_psfo_ngmix'].append(results[i]['T_PSFo'])
            output_dict[name]['T_err_psfo_ngmix'].append(results[i]['T_err_PSFo'])
            output_dict[name]['g1'].append(results[i][name]['g'][0])
            output_dict[name]['g1_err'].append(results[i][name]['pars_err'][2])
            output_dict[name]['g2'].append(results[i][name]['g'][1])
            output_dict[name]['g2_err'].append(results[i][name]['pars_err'][3])
            output_dict[name]['T'].append(results[i][name]['T'])
            output_dict[name]['T_err'].append(results[i][name]['T_err'])
            output_dict[name]['Tpsf'].append(results[i][name]['Tpsf'])
            try:
                output_dict[name]['s2n'].append(results[i][name]['s2n'])
            except:
                output_dict[name]['s2n'].append(results[i][name]['s2n_r'])
            output_dict[name]['flags'].append(results[i][name]['flags'])
            output_dict[name]['mcal_flags'].append(results[i]['mcal_flags'])

    return output_dict


# def compile_results_ngmix(results):
#     """ Compile results

#     Prepare the results of ngmix before saving.

#     Parameters
#     ----------
#     results : dict
#         Dictionary containing the results of ngmix metacal.

#     Returns
#     -------
#     output_dict : dict
#         Dictionary containing ready to be saved.

#     """

#     names = ['noshear']
#     names2 = ['id', 'n_epoch_model', 'psf_true_e1', 'psf_true_e2', 'psf_true_e1m', 'psf_true_e2m', 'g1', 'g1_err', 'g2', 'g2_err', 'T', 'T_err', 'Tpsf', 's2n', 'flags', 'mcal_flags']
#     output_dict = {k: {kk: [] for kk in names2} for k in names}
#     for i in range(len(results)):
#         for name in names:
#             output_dict[name]['id'].append(results[i]['obj_id'])
#             output_dict[name]['n_epoch_model'].append(results[i]['n_epoch_model'])
#             output_dict[name]['psf_true_e1'].append(results[i]['psf_true_e1'])
#             output_dict[name]['psf_true_e2'].append(results[i]['psf_true_e2'])
#             output_dict[name]['psf_true_e1m'].append(np.mean(results[i]['psf_true_e1']))
#             output_dict[name]['psf_true_e2m'].append(np.mean(results[i]['psf_true_e2']))
#             output_dict[name]['g1'].append(results[i][name]['g'][0])
#             output_dict[name]['g1_err'].append(results[i][name]['pars_err'][2])
#             output_dict[name]['g2'].append(results[i][name]['g'][1])
#             output_dict[name]['g2_err'].append(results[i][name]['pars_err'][3])
#             output_dict[name]['T'].append(results[i][name]['T'])
#             output_dict[name]['T_err'].append(results[i][name]['T_err'])
#             output_dict[name]['Tpsf'].append(results[i][name]['Tpsf'])
#             output_dict[name]['s2n'].append(results[i][name]['s2n'])
#             output_dict[name]['flags'].append(results[i][name]['flags'])
#             output_dict[name]['mcal_flags'].append(results[i]['mcal_flags'])

#     return output_dict


def save_results(output_dict, output_name):
    """ Save results

    Save the results into a fits file.

    Parameters
    ----------
    output_dict : dict
        Dictionary containing the results.
    output_name : str
        Name of the output file.

    """

    f = io.FITSCatalog(output_name, open_mode=io.BaseCatalog.OpenMode.ReadWrite)

    for key in output_dict.keys():
        f.save_as_fits(output_dict[key], ext_name=key.upper())


# def process(tile_cat_path, sm_cat_path, gal_vignet_path, bkg_vignet_path,
#             psf_vignet_path, weight_vignet_path, flag_vignet_path,
#             f_wcs_path, w_log):
def process(main_file_path, w_log):
    """ Process

    Process function.

    Parameters
    ----------
    tile_cat_path : str
        Path to the tile SExtractor catalog.
    gal_vignet_path : str
        Path to the galaxy vignets catalog.
    bkg_vignet_path : str
        Path to the background vignets catalog.
    psf_vignet_path : str
        Path to the PSF vignets catalog.
    weight_vignet_path : str
        Path to the weight vignets catalog.
    flag_vignet_path : str
        Path to the flag vignets catalog.
    f_wcs_path : str
        Path to the log file containing the WCS for each CCDs.

    Returns
    -------
    final_res : dict
        Dictionary containing the ngmix metacal results.

    """

    # tile_cat = io.FITSCatalog(tile_cat_path, SEx_catalog=True)
    # tile_cat.open()
    # obj_id = np.copy(tile_cat.get_data()['NUMBER'])
    # tile_vign = np.copy(tile_cat.get_data()['VIGNET'])
    # tile_flag = np.copy(tile_cat.get_data()['FLAGS'])
    # tile_imaflag = np.copy(tile_cat.get_data()['IMAFLAGS_ISO'])
    # tile_ra = np.copy(tile_cat.get_data()['XWIN_WORLD'])
    # tile_dec = np.copy(tile_cat.get_data()['YWIN_WORLD'])
    # tile_cat.close()
    # sm_cat = io.FITSCatalog(sm_cat_path, SEx_catalog=True)
    # sm_cat.open()
    # sm = np.copy(sm_cat.get_data()['SPREAD_MODEL'])
    # sm_err = np.copy(sm_cat.get_data()['SPREADERR_MODEL'])
    # sm_cat.close()
    # f_wcs_file = np.load(f_wcs_path).item()
    # gal_vign_cat = SqliteDict(gal_vignet_path)
    # bkg_vign_cat = SqliteDict(bkg_vignet_path)
    # psf_vign_cat = SqliteDict(psf_vignet_path)
    # weight_vign_cat = SqliteDict(weight_vignet_path)
    # flag_vign_cat = SqliteDict(flag_vignet_path)

    cat = SqliteDict(main_file_path)
    #cat = np.load(main_file_path)
    # cat_size = len(list(cat.keys()))
    cat_size = 50
    n_epoch = len(cat['0']['galsim_image'])
    # n_epoch = 1
    vign_size = np.shape(cat['0']['galsim_image'][0].array)
    flag_map = np.zeros(vign_size)

    final_res = []
    prior = get_prior()
    # iter_list = list(range(0,500)) + list(range(5000,5500))
    for i in range(cat_size):
        print(i)
        w_log.info('{}'.format(i))
        # Preselection step
        # if (tile_flag[i_tile] > 1) or (tile_imaflag[i_tile] > 0):
        #     continue
        # if (sm[i_tile] + (5. / 3.) * sm_err[i_tile] < 0.01) and (np.abs(sm[i_tile] + (5. / 3.) * sm_err[i_tile]) > 0.003):
        #     continue
        gal_vign = []
        psf_vign = []
        sigma_psf = []
        weight_vign = []
        flag_vign = []
        jacob_list = []
        psf_true_e1 = []
        psf_true_e2 = []
        psf_true_sigma = []
        # if (psf_vign_cat[str(id_tmp)] == 'empty') or (gal_vign_cat[str(id_tmp)] == 'empty'):
        #     continue
        # psf_expccd_name = list(psf_vign_cat[str(id_tmp)].keys())
        for n_e in range(n_epoch):
            psf_true_e1.append(cat[str(i)]['PSF']['e1_true'][n_e])
            psf_true_e2.append(cat[str(i)]['PSF']['e2_true'][n_e])
            psf_true_sigma.append(cat[str(i)]['PSF']['fwhm'][n_e] / 2.355)

            gal_vign.append(cat[str(i)]['galsim_image'][n_e].array)
            # if len(np.where(gal_vign_tmp.ravel() == 0)[0]) != 0:
            #     continue

            # psf_vign.append(cat[str(i)]['PSF']['psf_image'][n_e])
            psf_obj = cat[str(i)]['PSF']['galsim_psf'][n_e]
            wcs_tmp = cat[str(i)]['wcs'][n_e]
            wcs_x = cat[str(i)]['PSF']['X'][n_e]
            wcs_y = cat[str(i)]['PSF']['Y'][n_e]
            galsim_wcs_psf = local_wcs(wcs_tmp, wcs_x, wcs_y)
            psf_vign_tmp = psf_obj.drawImage(nx=51, ny=51, wcs=galsim_wcs_psf).array
            psf_vign.append(psf_vign_tmp)
            sigma_psf.append(cat[str(i)]['PSF']['fwhm'][n_e] / 2.355)

            # bkg_vign_tmp = bkg_vign_cat[str(id_tmp)][expccd_name_tmp]['VIGNET']
            # gal_vign_sub_bkg = gal_vign_tmp - bkg_vign_tmp
            # gal_vign.append(gal_vign_sub_bkg)

            weight_vign.append(cat[str(i)]['weight_map'][n_e].array)

            # tile_vign_tmp = np.copy(tile_vign[i_tile])
            # flag_vign_tmp = flag_vign_cat[str(id_tmp)][expccd_name_tmp]['VIGNET']
            # flag_vign_tmp[np.where(tile_vign_tmp == -1e30)] = 2**10
            # v_flag_tmp = flag_vign_tmp.ravel()
            # if len(np.where(v_flag_tmp != 0)[0])/(51*51) > 1/3.:
            #     continue
            flag_vign.append(flag_map)

            # exp_name, ccd_n = re.split('-', expccd_name_tmp)
            jacob_list.append(get_jacob(cat[str(i)]['wcs'][n_e],
                                        cat[str(i)]['PSF']['X'][n_e],
                                        cat[str(i)]['PSF']['Y'][n_e]))
        if len(gal_vign) == 0:
            continue
        if (len(gal_vign) != len(psf_vign)) | (len(gal_vign) != len(jacob_list)):
            continue
        try:
            res = do_ngmix_metacal(gal_vign,
                                psf_vign,
                                sigma_psf,
                                weight_vign,
                                flag_vign,
                                jacob_list,
                                prior)
        # res = do_ngmix(gal_vign,
        #                psf_vign,
        #                sigma_psf,
        #                weight_vign,
        #                flag_vign,
        #                jacob_list,
        #                prior)
        except Exception as e:
            w_log.info('ngmix fail on object {}\n{}'.format(i, e))
            continue
        res['obj_id'] = i
        res['n_epoch_model'] = 1 #  len(gal_vign)
        res['psf_true_e1'] = psf_true_e1
        res['psf_true_e2'] = psf_true_e2
        res['psf_true_sigma'] = psf_true_sigma
        final_res.append(res)

    # gal_vign_cat.close()
    # bkg_vign_cat.close()
    # flag_vign_cat.close()
    # weight_vign_cat.close()
    # psf_vign_cat.close()
    cat.close()

    return final_res


@module_runner(input_module=['sextractor_runner', 'psfexinterp_runner', 'vignetmaker_runner'],
               version='0.0.1',
               file_pattern=['tile_sexcat', 'image', 'exp_background', 'galaxy_psf', 'weight', 'flag'],
               file_ext=['.fits', '.sqlite', '.sqlite', '.sqlite', '.sqlite', '.sqlite'],
               depends=['numpy', 'ngmix', 'galsim'])
def ngmix_simu_runner(input_file_list, output_dir, file_number_string,
                      config, w_log):

    output_name = output_dir + '/' + 'ngmix' + file_number_string + '.fits'

    # f_wcs_path = config.getexpanded('NGMIX_RUNNER', 'LOG_WCS')

    metacal_res = process(input_file_list[0], w_log)
    res_dict = compile_results(metacal_res)
    # res_dict = compile_results_ngmix(metacal_res)
    save_results(res_dict, output_name)

    return None, None