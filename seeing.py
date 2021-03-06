######################################################################
# Seeing module written for the SBIG seeing monitor at the Thacher
# Observatory. Individual routines (should) have header comments.
#
# To do:
# ------
# 
# History:
# --------
# jswift  2/8/2015: First versions of get_data, fwhm_ave, fwhm_all,
#                   and fwhm_stats written
#
# jswift  4/1/2015: Vetted all FWHM data
# jswift 4/15/2015: Added simple histogram plotting function.

#
# dklink 4/25/2015: Wrote daygrapher
#                   Added empty/weird string handling and nan removal to FWHM_ave
#                   Added high-value data vetting (>50) to vetter
#
# dklink 4/30/2015: Finished get_FWHM_data_range
#                   Wrote graph_FWHM_data_range
#
######################################################################

import numpy as np
import matplotlib.pyplot as plt
import time
from scipy.stats import sigmaclip
from scipy.stats.kde import gaussian_kde
from scipy.interpolate import interp1d
import matplotlib as mpl
import datetime, glob, math
from length import length

def plot_params(fontsize=16,linewidth=1.5):
    """
    Procedure to set the parameters for this suite of plotting utilities
    """
    
    global fs,lw

    mpl.rcParams['axes.linewidth'] = 1.5
    mpl.rcParams['xtick.major.size'] = 5
    mpl.rcParams['xtick.major.width'] = 1.5
    mpl.rcParams['ytick.major.size'] = 5
    mpl.rcParams['ytick.major.width'] = 1.5
    mpl.rcParams['xtick.labelsize'] = 14
    mpl.rcParams['ytick.labelsize'] = 14
    fs = fontsize
    lw = linewidth

    return

def distparams(dist):
    """
    Description:
    ------------
    Return robust statistics of a distribution of data values

    Example:
    --------
    med,mode,interval,lo,hi = distparams(dist)
    """

    from scipy.stats.kde import gaussian_kde
    from scipy.interpolate import interp1d
    vals = np.linspace(np.min(dist)*0.5,np.max(dist)*1.5,1000)
    kde = gaussian_kde(dist)
    pdf = kde(vals)
    dist_c = np.cumsum(pdf)/np.sum(pdf)
    func = interp1d(dist_c,vals,kind='linear')
    lo = np.float(func(math.erfc(1./np.sqrt(2))))
    hi = np.float(func(math.erf(1./np.sqrt(2))))
    med = np.float(func(0.5))
    mode = vals[np.argmax(pdf)]

    disthi = np.linspace(.684,.999,100)
    distlo = disthi-0.6827
    disthis = func(disthi)
    distlos = func(distlo)
    
    interval = np.min(disthis-distlos)

    return med,mode,interval,lo,hi



def get_data(year=2015,month=3,day=6,tenmin=False,
             path='/home/douglas/Dropbox (Thacher)/Observatory/Seeing/Data/',
             filename = ''):

    """
    Description:
    ------------
    Fetch data from the seeing monitor for a given date
    

    Example:
    --------
    data = get_data(year=2015,month=3,day=6)
    or
    data = get_data(filename='/home/douglas/Dropbox (Thacher)/Observatory/Seeing/Data/')


    To do:
    ------
    Make data reading more robust

    !!! First line of data for FWHMraw has formatting errors

    """

    # Set up path and filename
    prefix = 'seeing_log_'
    root = str(year)+'-'+str(month)+'-'+str(day)
    suffix = '.log'

    if filename == '':
        file = path+prefix+root+suffix
    else:
        file = filename

    # Read first section of data (tab delimited and uniform)
    d1 = np.loadtxt(file, dtype=[('time', '|S8'), ('date', '|S10'), ('Fmin', np.int),
                                 ('Fmax', np.int), ('FWHMave', np.float), ('npts', np.int)],
                    usecols=(0,1,2,3,4,5))
    
    # Read in second section of data (; delimited and not uniform)
    d2raw = np.loadtxt(file, delimiter=[0],dtype='str')
    d2 = []
    for i in np.arange(len(d2raw)):
        d2.append(d2raw[i][37:90].split(';')[0:-1])

    # create null vectors of interest
    yearv = [] ; monthv = [] ; dayv = [] ; doyv = [] ; time24v = [] ; dt =[]

    # parse data
    
    date = d1['date']
    time = d1['time']
    
    for i in range(len(date)):
        yr = np.int(date[i].split('/')[2])
        yearv = np.append(yearv,yr)

        month = np.int(date[i].split('/')[0])
        monthv = np.append(monthv,month)
        
        day = np.int(date[i].split('/')[1])
        dayv = np.append(dayv,day)
        
        hr  = np.int(time[i].split(':')[0])
        mn  = np.int(time[i].split(':')[1])
        sec = np.int(time[i].split(':')[2])

        time24v = np.append(time24v,hr+mn/60.0+sec/3600.0)

        d = datetime.datetime(yr,month,day,hr,mn,sec,0)
        dt = np.append(dt,d)
        doyv = np.append(doyv,d.timetuple().tm_yday+np.float(hr)/
                         24.0+mn/(24.0*60.0)+sec/(24.0*3600.0))

    d1time = d1['time']; d1date = d1['date']; d1fmin = d1['Fmin']
    d1fmax = d1['Fmax']; d1fave = d1['FWHMave']; d1npts = d1['npts']
    
    if tenmin and year <= 2015 and month <= 4:
        dt = dt[::10]
        doyv = doyv[::10]
        time24v = time24v[::10]
        d1time = d1time[::10]
        d1date = d1date[::10]
        d1fmin = d1fmin[::10]
        d1fmax = d1fmax[::10]
        d1fave = d1fave[::10]
        d1npts = d1npts[::10]
        d2 = d2[::10]
        
    # Put all data together into a dictionary
    data = {"datetime": dt, "doy": doyv, "timefloat": time24v,
            "time": d1time, "date": d1date,"Fmin": d1fmin, "Fmax": d1fmax,
            "FWHMave": d1fave, "npts": d1npts,"FWHMraw": d2}

    return data


def FWHM_all(data):
    """
    Description:
    ------------
    Extract a numpy array of all FWHM measurements vetted against zeros and 0.08 values
    which seem to be a saturation effect
    """

    raw = data["FWHMraw"]
    new = []
    for r in raw:
        new = np.append(new,r)

    inds, = np.where(new == '')

    if inds:
        new[inds] = '0.0'

    FWHM = new.astype('float')

    keep, = np.where((FWHM != 0.0) & (FWHM != 0.08))
    
    return FWHM[keep]


def FWHM_ave(data,clip=False,sigmas=False):
    """
    Description:
    ------------    
    Computes the average FWHM
    Expects data dictionary in format of "get_data"

    """

    raw = data['FWHMraw']
    
    sz = len(raw)
    FWHM = np.ones(sz)* np.nan
    sigma = np.ones(sz)* np.nan
    for i in range(sz):
        #remove empty strings from data before processing
        if '' in raw[i]:
            raw[i].remove('')
            
        #safeguard against wierd string formatting errors
        try:
            vals = np.array(raw[i]).astype('float')
        except ValueError:
            vals = [0]
        
        
        if clip:
            newvals, low, high = sigmaclip(vals,low=clip,high=clip)
            FWHM[i] = np.mean(newvals)
            sigma[i] = np.std(newvals)
        else:
            FWHM[i] = np.mean(vals)
            sigma[i] = np.std(vals)

    FWHM = np.nan_to_num(FWHM)
    if sigmas:
        return [FWHM,sigma]
    else:
        return FWHM


def FWHM_stats(data,all=True,clip=False):
    """
    Description:
    ------------
    Return basic FWHM stats
    """
    
    if all:
        fwhm =  FWHM_all(data)
    elif clip:
        fwhm = FWHM_ave(data,clip=clip)
    else:
        fwhm = FWHM_ave(data)


    # Basic stats
    med = np.median(fwhm)
    mean = np.mean(fwhm)
    fwhm_clip, low, high = sigmaclip(fwhm,low=3,high=3)
    meanclip = np.mean(fwhm_clip)

    # Get mode using kernel density estimation (KDE)
    vals = np.linspace(0,30,1000)
    fkde = gaussian_kde(fwhm)
    fpdf = fkde(vals)
    mode = vals[np.argmax(fpdf)]

    std = np.std(fwhm)
    
    return [mean,med,mode,std,meanclip]
    

    

def vet_FWHM_series(time,raw):

    """
    Description:
    ------------
    Extract a numpy array of all FWHM measurements vetted against zeros and 0.08 values
    which seem to be a saturation effect
    
    Timestamp for data is also input so that vetted data contains corresponding
    timestamp.
    
    Also vets values over 50, which appear to come in as the sun is rising and setting

    
    """

    new = []
    newt = []
    for r in raw:
        new = np.append(new,round(r,2))

    for t in time:
        newt = np.append(newt,t)

    if length(newt) != length(new):
        print 'Time and data vectors not equal lengths!'
        return None,None

    inds, = np.where(new == '')

    if inds:
        new[inds] = '0.0'

    keep1, = np.where(new != 0.0)
    new = new[keep1]
    newt = newt[keep1]

    keep2, = np.where(new != 0.08)
    new = new[keep2]
    newt = newt[keep2]
    
    keep3, = np.where(new < 10)
    new = new[keep3]
    newt = newt[keep3]
    
    FWHM = new.astype('float')

    return newt, FWHM



def fwhm_hist(vec,bins=50):

    plot_params()
    plt.ion()
    plt.figure(33)
    plt.clf()
    maxval = np.max(vec)
    minval = np.min(vec)
    std = np.std(vec)
    med = np.median(vec)

    vec = vec[vec < 5*std+med]
    plt.hist(vec,bins=bins)
    plt.xlabel('FWHM (arcsec)',fontsize=fs)
    plt.ylabel('Frequency',fontsize=fs)

    mpl.rcdefaults()
    return


def FWHM_day_graph(year=2015, month=3, day=15,
                   path='/home/douglas/Dropbox (Thacher)/Observatory/Seeing/Data/'):
    """
    Description:
    ------------
    Get FWHM data from the given day, vet it, and then display it in a histogram.
    """
    
    data = get_data(year, month, day,path=path) #assumes default path is correct
    FWHM_data = FWHM_ave(data)
    time = data['timefloat']
    
    vetted_data = vet_FWHM_series(time,FWHM_data)[1]
    if len(vetted_data) == 0:
        print "Wow, that day really had shitty data."
    else:
        fwhm_hist(vetted_data)
    

    mpl.rcdefaults()
    return

def get_FWHM_data_range(start_date=datetime.datetime(2015,3,1),
                        end_date=datetime.datetime(2015,4,15),tenmin=True,
                   path='/home/douglas/Dropbox (Thacher)/Observatory/Seeing/Data/'):

    files = glob.glob(path+'seeing_log*.log')

    keepfiles = []
    for f in files:
        datestr = f.split('_')[-1].split('.')[0]
        date = datetime.datetime(np.int(datestr.split('-')[0]),\
                                  np.int(datestr.split('-')[1]),\
                                  np.int(datestr.split('-')[2]))
        if date >= start_date and date <= end_date:
            keepfiles.append(f)

    # Need to loop through these files and accumulate data

    all_FWHM_data = []
    
    for fname in keepfiles:
        temp_data = get_data(filename=fname,tenmin=tenmin)
        FWHM_data = FWHM_ave(temp_data)
        time = temp_data['timefloat']
        
        vetted_data = vet_FWHM_series(time,FWHM_data)[1]
        all_FWHM_data.extend(vetted_data)
            
    return all_FWHM_data


def graph_FWHM_data_range(start_date=datetime.datetime(2015,3,6),
                          end_date=datetime.datetime(2015,4,15),tenmin=True,
                          path='/home/douglas/Dropbox (Thacher)/Observatory/Seeing/Data/',
                          write=True,outpath='./'):
    
    
    plot_params()
    fwhm = get_FWHM_data_range(start_date = start_date, end_date=end_date, path=path, tenmin=tenmin)

    # Basic stats
    med = np.median(fwhm)
    mean = np.mean(fwhm)
    fwhm_clip, low, high = sigmaclip(fwhm,low=3,high=3)
    meanclip = np.mean(fwhm_clip)

    # Get mode using kernel density estimation (KDE)
    vals = np.linspace(0,30,1000)
    fkde = gaussian_kde(fwhm)
    fpdf = fkde(vals)
    mode = vals[np.argmax(fpdf)]
    std = np.std(fwhm)


    plt.ion()
    plt.figure(99)
    plt.clf()
    plt.hist(fwhm, color='darkgoldenrod',bins=35)
    plt.xlabel('FWHM (arcsec)',fontsize=16)
    plt.ylabel('Frequency',fontsize=16)
    plt.annotate('mode $=$ %.2f" ' % mode, [0.87,0.85],horizontalalignment='right',
                 xycoords='figure fraction',fontsize='large')
    plt.annotate('median $=$ %.2f" ' % med, [0.87,0.8],horizontalalignment='right',
                 xycoords='figure fraction',fontsize='large')
    plt.annotate('mean $=$ %.2f" ' % mean, [0.87,0.75],horizontalalignment='right',
                 xycoords='figure fraction',fontsize='large')

    xvals = np.linspace(0,30,1000)
    kde = gaussian_kde(fwhm)
    pdf = kde(xvals)
    dist_c = np.cumsum(pdf)/np.sum(pdf)
    func = interp1d(dist_c,vals,kind='linear')
    lo = np.float(func(math.erfc(1./np.sqrt(2))))
    hi = np.float(func(math.erf(1./np.sqrt(2))))

    disthi = np.linspace(.684,.999,100)
    distlo = disthi-0.6827
    disthis = func(disthi)
    distlos = func(distlo)

    interval = np.min(disthis-distlos)

    plt.annotate('1 $\sigma$ int. $=$ %.2f" ' % interval, [0.87,0.70],horizontalalignment='right',
                 xycoords='figure fraction',fontsize='large')
    
    
    plt.rcdefaults()

    plt.savefig(outpath+'Seeing_Cumulative.png',dpi=300)

    return
