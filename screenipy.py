#!/usr/bin/python3

import os
import sys
import urllib
import requests
import yfinance as yf
from nsetools import Nse
import numpy as np
import pandas as pd
from tabulate import tabulate
import configparser
from time import sleep
import platform
import datetime

# Try Fixing bug with this symbol
TEST_STKCODE = "HAPPSTMNDS"

# Decoration Class
class colorText:
	HEAD = '\033[95m'
	BLUE = '\033[94m'
	GREEN = '\033[92m'
	WARN = '\033[93m'
	FAIL = '\033[91m'
	END = '\033[0m'
	BOLD = '\033[1m'
	UNDR = '\033[4m'

# Constants
DEBUG = False
VERSION = "1.0b"
consolidationPercentage = 4
volumeRatio = 2.5
minLTP = 20.0
maxLTP = 50000
period = '365d'
duration = '1d'
daysToLookback = 20

art = colorText.GREEN + '''
     .d8888b.                                             d8b                   
    d88P  Y88b                                            Y8P                   
    Y88b.                                                                       
     "Y888b.    .d8888b 888d888 .d88b.   .d88b.  88888b.  888 88888b.  888  888 
        "Y88b. d88P"    888P"  d8P  Y8b d8P  Y8b 888 "88b 888 888 "88b 888  888 
          "888 888      888    88888888 88888888 888  888 888 888  888 888  888 
    Y88b  d88P Y88b.    888    Y8b.     Y8b.     888  888 888 888 d88P Y88b 888 
     "Y8888P"   "Y8888P 888     "Y8888   "Y8888  888  888 888 88888P"   "Y88888 
                                                              888           888 
                                                              888      Y8b d88P 
                                                              888       "Y88P"  

''' + colorText.END

nse = Nse()
np.seterr(divide='ignore', invalid='ignore')
parser = configparser.ConfigParser()

# Global Variabls
screenResults = pd.DataFrame(columns=['Stock','Consolidating','Breaking-Out','MA-Signal','Volume','LTP'])
saveResults = pd.DataFrame(columns=['Stock','Consolidating','Breaking-Out','MA-Signal','Volume','LTP'])
screeningDictionary = {
    'Stock': "",
    'Consolidating': "",
    'Breaking-Out': "",
    'MA-Signal': "",
    'Volume': "",
    'LTP': 0
}
saveDictionary = {
    'Stock': "",
    'Consolidating': "",
    'Breaking-Out': "",
    'MA-Signal': "",
    'Volume': "",
    'LTP': 0
}
listStockCodes = []

# Get system wide proxy for networking
try:
    proxyServer = urllib.request.getproxies()['http']
except KeyError:
    proxyServer = ""

def clearScreen():
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')
    print(art)

# Fetch all stock codes from NSE
def fetchStockCodes():
    global listStockCodes
    print(colorText.BOLD + "[+] Getting Stock Codes From NSE... ", end='')
    listStockCodes = list(nse.get_stock_codes(cached=False))[1:]
    if len(listStockCodes) > 10:
        print(colorText.GREEN + ("=> Done! Fetched %d stock codes." % len(listStockCodes)) + colorText.END)
    else:
        print(colorText.FAIL + "=> Error getting stock codes from NSE!" + colorText.END)
        sys.exit("Exiting script..")

# Fetch stock price data from Yahoo finance
def fetchStockData(stockCode):
    data = yf.download(
        tickers = stockCode+".NS",
        period = period,
        duration = duration,
        proxy = proxyServer,
        progress=False
    )
    sys.stdout.write("\r\033[K")
    print(colorText.BOLD + colorText.GREEN + ("Fetching data & Analyzing %s..." % stockCode) + colorText.END, end='')
    if len(data) == 0:
        print(colorText.BOLD + colorText.FAIL + "=> Failed to fetch!" + colorText.END, end='\r', flush=True)
        return None
    print(colorText.BOLD + colorText.GREEN + "=> Done!" + colorText.END, end='\r', flush=True)
    return data

# Preprocess the acquired data
def preprocessData(data, daysToLookback=daysToLookback):
    sma = data.rolling(window=50).mean()
    lma = data.rolling(window=200).mean()
    vol = data.rolling(window=20).mean()
    data.insert(6,'SMA',sma['Close'])
    data.insert(7,'LMA',lma['Close'])
    data.insert(8,'VolMA',vol['Volume'])
    data = data[::-1]               # Reverse the dataframe
    data = data.head(daysToLookback)
    data = data.replace(np.nan, 0)
    if DEBUG:
        print(data)
    return data

# Linear regression
def showBoxfitLine(data,daysToLookback=daysToLookback, stockCode=''):
    x = np.arange(daysToLookback+1,1,-1)
    y = np.array(data)
    m,c = np.polyfit(x,y,1)
    print("Slope = %f\tIntercept = %f\tLine of angle with X-axis = %f" % (round(m,2),round(c,2),np.rad2deg(np.arctan(m))))
    plt.plot(x,y,'o')
    plt.plot(x,m*x+c)
    plt.xlabel("Days")
    plt.ylabel("Price")
    plt.title(stockCode)
    plt.show()

# Simple Average
def showBoxfitLineAverage(data,daysToLookback=daysToLookback, stockCode=''):
    x = np.arange(daysToLookback+1,1,-1)
    y = np.array(data)
    z = np.ones(daysToLookback) * y.mean()
    print("Intercept = %f" % z[0])
    plt.plot(x,y,'o')
    plt.plot(x,z)
    plt.xlabel("Days")
    plt.ylabel("Price")
    plt.title(stockCode)
    plt.show()

# Validate LTP within limits
def validateLTP(data, dict, saveDict, minLTP=minLTP, maxLTP=maxLTP):
    recent = data.head(1)
    ltp = round(recent['Close'][0],2)
    saveDict['LTP'] = str(ltp)
    if(ltp >= minLTP and ltp <= maxLTP):
        dict['LTP'] = colorText.GREEN + str(ltp) + colorText.END
        return True
    else:
        dict['LTP'] = colorText.FAIL + str(ltp) + colorText.END
        return False

# Validate if share prices are consolidating
def validateConsolidation(data, dict, saveDict, percentage=2.5):
    hc = data.describe()['Close']['max']
    lc = data.describe()['Close']['min']
    if ((hc - lc) <= (hc*percentage/100) and (hc - lc != 0)):
        dict['Consolidating'] = colorText.BOLD + colorText.GREEN + "Range = " + str(round((abs((hc-lc)/hc)*100),2))+"%" + colorText.END
        if DEBUG:
            print("Consolidation => Valid!")
    else:
        if DEBUG:
            print("Consolidation => Invalid!")
        dict['Consolidating'] = colorText.BOLD + colorText.FAIL + "Range = " + str(round((abs((hc-lc)/hc)*100),2)) + "%" + colorText.END
    saveDict['Consolidating'] = str(round((abs((hc-lc)/hc)*100),2))+"%"
    return round((abs((hc-lc)/hc)*100),2)

# Validate Moving averages
def validateMovingAverages(data, dict, saveDict):
    recent = data.head(1)
    if(recent['SMA'][0] > recent['LMA'][0] and recent['Close'][0] > recent['SMA'][0]):
        dict['MA-Signal'] = colorText.BOLD + colorText.GREEN + 'Bullish' + colorText.END
        saveDict['MA-Signal'] = 'Bullish'
    elif(recent['SMA'][0] < recent['LMA'][0]):
        dict['MA-Signal'] = colorText.BOLD + colorText.FAIL + 'Bearish' + colorText.END
        saveDict['MA-Signal'] = 'Bearish'
    else:
        dict['MA-Signal'] = colorText.BOLD + colorText.WARN + 'Neutral' + colorText.END
        saveDict['MA-Signal'] = 'Neutral'

# Validate if volume of last day is higher than avg
def validateVolume(data, dict, saveDict, volumeRatio=2.5):
    recent = data.head(1)
    ratio = round(recent['Volume'][0]/recent['VolMA'][0],2)
    saveDict['Volume'] = str(ratio)+"x"
    if(ratio >= volumeRatio):
        dict['Volume'] = colorText.BOLD + colorText.GREEN + str(ratio) + "x" + colorText.END
        return True
    else:
        dict['Volume'] = colorText.BOLD + colorText.FAIL + str(ratio) + "x" + colorText.END
        return False

# Find accurate breakout value
def findBreakout(data, dict, saveDict, daysToLookback):
    recent = data.head(1)
    data = data[1:]
    hs = round(data.describe()['High']['max'],2)
    hc = round(data.describe()['Close']['max'],2)
    rc = round(recent['Close'][0],2)
    if hs > hc:
        if ((hs - hc) <= (hs*2/100)):
            saveDict['Breaking-Out'] = str(hc)
            if rc >= hc:
                dict['Breaking-Out'] = colorText.BOLD + colorText.GREEN + "Yes (BO: " + str(hc) + " R: " + str(hs) + ")" + colorText.END
                return True
            else:
                dict['Breaking-Out'] = colorText.BOLD + colorText.FAIL + "NO (BO: " + str(hc) + " R: " + str(hs) + ")" + colorText.END
                return False
        else:    
            noOfHigherShadows = len(data[data.High > hc])
            if(daysToLookback/noOfHigherShadows <= 3):
                saveDict['Breaking-Out'] = str(hs)
                if rc >= hs:
                    dict['Breaking-Out'] = colorText.BOLD + colorText.GREEN + "Yes (BO: " + str(hs) + ")" + colorText.END
                    return True
                else:
                    dict['Breaking-Out'] = colorText.BOLD + colorText.FAIL + "NO (BO: " + str(hs) + ")" + colorText.END
                    return False
            else:
                saveDict['Breaking-Out'] = str(hc) + ", " + str(hs)
                if rc >= hc:
                    dict['Breaking-Out'] = colorText.BOLD + colorText.GREEN + "Yes (BO: " + str(hc) + " R: " + str(hs) + ")" + colorText.END
                    return True
                else:
                    dict['Breaking-Out'] = colorText.BOLD + colorText.FAIL + "NO (BO: " + str(hc) + " R: " + str(hs) + ")" + colorText.END
                    return False
    else:
        saveDict['Breaking-Out'] = str(hc)
        if rc >= hc:
            dict['Breaking-Out'] = colorText.BOLD + colorText.GREEN + "Yes (BO: " + str(hc) + ")" + colorText.END
            return True
        else:
            dict['Breaking-Out'] = colorText.BOLD + colorText.FAIL + "NO (BO: " + str(hc) + ")" + colorText.END
            return False


# Handle user input and save config
def setConfig(parser):
    parser.add_section('config')
    print('')
    print(colorText.BOLD + colorText.GREEN +'[+] Screeni-py User Configuration:' + colorText.END)
    period = input('[+] Enter number of days for which stock data to be downloaded (Days)(Default = 365): ')
    daysToLookback = input('[+] Number of recent days to screen for Breakout/Consolidation (Days)(Default = 45): ')
    duration = input('[+] Enter Duration of each candle (Days)(Default = 1): ')
    minLTP = input('[+] Minimum Price of Stock to Buy (in RS)(Default = 20): ')
    maxLTP = input('[+] Maximum Price of Stock to Buy (in RS)(Default = 50000): ')
    volumeRatio = input('[+] How many times the volume should be more than average for the breakout? (Number)(Default = 2.5): ')
    consolidationPercentage = input('[+] How many % the price should be in range to consider it as consolidation? (Number)(Default = 4): ')
    parser.set('config','period',period + "d")
    parser.set('config','daysToLookback',daysToLookback)
    parser.set('config','duration',duration + "d")
    parser.set('config','minPrice',minLTP)
    parser.set('config','maxPrice',maxLTP)
    parser.set('config','volumeRatio',volumeRatio)
    parser.set('config','consolidationPercentage',consolidationPercentage)
    try:
        fp = open('screenipy.ini','w')
        parser.write(fp)
        fp.close()
        print(colorText.BOLD + colorText.GREEN +'[+] User configuration saved.' + colorText.END)
    except:
        print(colorText.BOLD + colorText.FAIL +'[+] Failed to save user config. Aborting..' + colorText.END)
        sys.exit(1)

# Load user config from file
def getConfig(parser):
    global duration, period, minLTP, maxLTP, volumeRatio, consolidationPercentage, daysToLookback
    if len(parser.read('screenipy.ini')):
        duration = parser.get('config','duration')
        period = parser.get('config','period')
        minLTP = float(parser.get('config','minprice'))
        maxLTP = float(parser.get('config','maxprice'))
        volumeRatio = float(parser.get('config','volumeRatio'))
        consolidationPercentage = float(parser.get('config','consolidationPercentage'))
        daysToLookback = int(parser.get('config','daysToLookback'))
        print(colorText.BOLD + colorText.GREEN +'[+] User configuration loaded.' + colorText.END)
    else:
        print(colorText.BOLD + colorText.FAIL + "[+] User config not found!" + colorText.END)
        print(colorText.BOLD + colorText.WARN + "[+] Configure the limits to continue." + colorText.END)
        setConfig(parser)

# Manage Execution flow
def initExecution():
    print(colorText.BOLD + colorText.WARN + '[+] Press a number to start stock screening: ' + colorText.END)
    print(colorText.BOLD + '''    1 > Screen stocks for Breakout or Consolidation
    2 > Screen only the stocks with recent Breakout & Volume
    3 > Screen only the Consolidating stocks
    4 > Edit user configuration
    5 > Show user configuration
    6 > About Developer
    7 > Exit''' + colorText.END
    )
    result = input(colorText.BOLD + colorText.FAIL + '[+] Select option: ')
    print(colorText.END, end='')
    try:
        result = int(result)
        if(result < 0 or result > 7):
            raise ValueError
        return result
    except:
        print(colorText.BOLD + colorText.FAIL + '\n[+] Please enter a valid numeric option & Try Again!' + colorText.END)
        sleep(2)
        clearScreen()
        return initExecution()

# Print config file
def showConfigFile():
    try:
        f = open('screenipy.ini','r')
        print(colorText.BOLD + colorText.GREEN +'[+] Screeni-py User Configuration:' + colorText.END)
        print("\n"+f.read())
        f.close()
    except:
        print(colorText.BOLD + colorText.FAIL + "[+] User Configuration not found!" + colorText.END)
        print(colorText.BOLD + colorText.WARN + "[+] Configure the limits to continue." + colorText.END)
        setConfig(parser)

if __name__ == "__main__":
    clearScreen()
    executeOption = initExecution()
    if executeOption == 4:
        setConfig(parser)
    if executeOption == 5:
        showConfigFile()
    if executeOption == 6:
        print(colorText.BOLD + colorText.WARN + "\n[+] Developer: Pranjal Joshi." + colorText.END)
        print(colorText.BOLD + colorText.WARN + ("[+] Version: %s" % VERSION) + colorText.END)
        print(colorText.BOLD + colorText.WARN + "[+] More: https://github.com/pranjal-joshi/Screeni-py" + colorText.END)
    if executeOption == 7:
        print(colorText.BOLD + colorText.FAIL + "[+] Script terminated by the user." + colorText.END)
        sys.exit(0)
    if executeOption > 0 and executeOption < 4:
        getConfig(parser)
        fetchStockCodes()
        print(colorText.BOLD + colorText.WARN + "[+] Starting Stock Screening.. Press Ctrl+C to stop!\n")
        for stock in listStockCodes:
            try:
                data = fetchStockData(stock)
                processedData = preprocessData(data, daysToLookback=daysToLookback)
                if not processedData.empty:
                    screeningDictionary['Stock'] = colorText.BOLD + colorText.BLUE + stock + colorText.END
                    saveDictionary['Stock'] = stock
                    consolidationValue = validateConsolidation(processedData, screeningDictionary, saveDictionary, percentage=consolidationPercentage)
                    validateMovingAverages(processedData, screeningDictionary, saveDictionary)
                    isVolumeHigh = validateVolume(processedData, screeningDictionary, saveDictionary, volumeRatio=volumeRatio)
                    isBreaking = findBreakout(processedData, screeningDictionary, saveDictionary, daysToLookback=daysToLookback)
                    isLtpValid = validateLTP(processedData, screeningDictionary, saveDictionary, minLTP=minLTP, maxLTP=maxLTP)
                    if (executeOption == 1 or executeOption == 2) and isBreaking and isVolumeHigh and isLtpValid:
                        screenResults = screenResults.append(screeningDictionary,ignore_index=True)
                        saveResults = saveResults.append(saveDictionary, ignore_index=True)
                    if (executeOption == 1 or executeOption == 3) and (consolidationValue <= consolidationPercentage and consolidationValue != 0) and isLtpValid:
                        screenResults = screenResults.append(screeningDictionary,ignore_index=True)
                        saveResults = saveResults.append(saveDictionary, ignore_index=True)
            except KeyboardInterrupt:
                print(colorText.BOLD + colorText.FAIL + "[+] Script terminated by the user." + colorText.END)
                break
            except Exception as e:
                print(colorText.FAIL + ("[+] Exception Occured while Screening %s! Skipping this stock.." % stock) + colorText.END)
                print(e)
        print(tabulate(screenResults, headers='keys', tablefmt='psql'))
        saveResults.to_excel('screenipy-result.xlsx')
        print(colorText.BOLD + colorText.GREEN + "[+] Results saved to screenipy-result.xlsx" + colorText.END)
        print(colorText.BOLD + colorText.GREEN + "[+] Screening Completed! Happy Trading! :)" + colorText.END)
        sys.exit(0)