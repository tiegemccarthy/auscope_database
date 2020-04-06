#!/usr/bin/python
import re
import os
import MySQLdb as mariadb
from astropy.io import ascii
import numpy as np
import SEFD_estimator
import scipy.optimize
from astropy.table import vstack
import sys

def extractRelevantSections(all_corr_sections):
    relevant_tags = ['STATION', 'DROP', 'MANUAL', 'SNR']
    relevant_sections = []
    for tag in relevant_tags:
        for section in all_corr_sections:
            if tag in section[0:15]:
                relevant_sections.append(section)
    return relevant_sections
    # This pulls the relevant sections out of the split corr report, it is required as sometimes corr reports have different 
    # number of sections and can cause the script to fail. This allows you to know exactly which section is which.

def droppedChannels(text_section):
    station_id = [['KATH12M', 'YARRA12M', 'HOBART12', 'HOBART26'], ['Ke', 'Yg', 'Hb', 'Ho'], ['a', 'i', 'd', 'H']]
    dropped_chans = []
    for ant in station_id[1]:
        regex = ant + '.*'
        dropped = re.findall(regex,text_section,re.MULTILINE)
        if dropped == []:
            dropped_chans.append('')            
        elif len(dropped[0]) < 4:
            dropped_chans.append('')
        else:
            dropped_chans.append(','.join(dropped))
    return dropped_chans  
    # This function takes a block of text, and scrapes out whether any AuScope antennas have dropped channels
    # The input of this function is a text section from the correlator report (section[5])
    
def manualPcal(text_section):
    station_id = [['KATH12M', 'YARRA12M', 'HOBART12', 'HOBART26'], ['Ke', 'Yg', 'Hb', 'Ho'], ['a', 'i', 'd', 'H']]
    manual_pcal = []
    for ant in station_id[1]:
        if ant in text_section:
            manual_pcal.append(True)
        else:
            manual_pcal.append(False)
    return manual_pcal
    # this determines whether manual pcal happened for any of our telescopes.
    # The input of this function is a text section from the correlator report (section[6])
    
def sefdTableExtract(text_section, antennas_corr_reference, antenna_reference):
    if len(text_section) > 20:
        # old corr files have an extra bit in the SNR table section we want removed
        regex = "CONTROL.*" #this may cause some issues
        has_control = re.findall(regex,text_section,re.MULTILINE)
        if len(has_control) > 0:
            text_section = text_section.split("CONTROL")[0]
        col_names = ['bl', 'X_snr', 'X_n', 'S_snr', 'S_n']
        snr_data = ascii.read(text_section, data_start=4, fast_reader=True, names=col_names)
        # Make sure antennas being extracted exist in both the corr-file and skd-file
        mask = np.isin(np.asarray(antennas_corr_reference)[:,0], np.asarray(antenna_reference)[:,1])
        # This next loop applies the restriction above, along with removing random symbols (like 1s).
        bad_bl_mask = []
        for i in range(0,len(snr_data['bl'])):
            bl = snr_data['bl'][i]
            if bl[0] not in list(np.asarray(antennas_corr_reference)[mask,1]) or bl[1] not in list(np.asarray(antennas_corr_reference)[mask,1]):
                bad_bl_mask.append(i)
        snr_data.remove_rows(bad_bl_mask)
        table_array = np.array([snr_data['X_snr'],snr_data['X_n'],snr_data['S_snr'],snr_data['S_n']])
        # Need to manipulate the array so it is the same as the table, can probably create the array more elegantly.
        corrtab = np.fliplr(np.rot90(table_array, k=1, axes=(1,0)))
        corrtab_split = np.hsplit(corrtab,2)
        corrtab_X = corrtab_split[0]
        corrtab_S = corrtab_split[1]
    else:
        print("No SNR table available!")
        snr_data = []
        corrtab_X = []
        corrtab_S = []
        # if snr table isnt included for some reason, this stops the script from crashing.
        # Instead SEFD estimation will be skipped.
    return snr_data, corrtab_X, corrtab_S

    
def antennaReference_CORR(text_section):
    regex = '\(.{4}\)'
    antennas_corr_report = re.findall(regex,text_section,re.MULTILINE)
    antennas_corr_reference = []
    for line in antennas_corr_report:
        if '/' in line:
            ref = [line[1:3],line[4]]
            antennas_corr_reference.append(ref)
        elif '-' in line: # this is to handle some funky corr report styles.
            ref = [line[3:5], line[1]]
            antennas_corr_reference.append(ref)
    return antennas_corr_reference
    # This function takes the section[4] of the corr report and gives the 2 character
    # station code plus the single character corr code.
    
def antennaReference_SKD(text_section):
    regex = "^A\s\s.*"
    alias_reference = re.findall(regex,text_section,re.MULTILINE)
    antenna_reference = []
    for entry in alias_reference:
        entry = entry.split()
        ref = [entry[2], entry[14], entry[15]]
        antenna_reference.append(ref)
    return antenna_reference

def predictedSEFDextract(text_section, antenna_reference):
    regex_sefd = "^T\s.*" #this may cause some issues
    sefd_skd = re.findall(regex_sefd,text_section,re.MULTILINE)
    stations_SEFD =[]
    for line in sefd_skd:
        line = line.split()
        for i in range(0, len(antenna_reference)):
            if line[1] == antenna_reference[i][2] or line[2] == antenna_reference[i][0]:
                SEFD_X_S = [antenna_reference[i][1], line[6], line[8]]
                stations_SEFD.append(SEFD_X_S)
    SEFD_tags = np.asarray(stations_SEFD)[:,0]
    SEFD_X = np.asarray(stations_SEFD)[:,1].astype(np.float)
    SEFD_S = np.asarray(stations_SEFD)[:,2].astype(np.float)
    return SEFD_tags, SEFD_X, SEFD_S
    # This block of code grabs all the SEFD setting lines and pulls the X and S SEFD for each station.
    
def basnumArray(snr_data, antennas_corr_reference, SEFD_tags):
    basnum = []
    for bl in snr_data['bl']:
        bl_pair = []
        for i in range(0, len(antennas_corr_reference)):
            if antennas_corr_reference[i][1] in bl:
                index = np.where(SEFD_tags == antennas_corr_reference[i][0])
                bl_pair.append(index[0])
        basnum.append(np.concatenate(bl_pair))
    basnum=np.stack(basnum, axis=0)
    return basnum

def main(exp_id, db_name):
    if os.path.isfile(os.getcwd()+"/corr_files/"+ exp_id + '.corr'):
        print("Beginning corr and skd file ingest for experiment " + exp_id + ".")
        with open(os.getcwd()+'/corr_files/'+ str(exp_id) + '.corr') as file:
            contents = file.read()
            corr_section = contents.split('\n+')
            if len(corr_section) < 3: # another ad-hoc addition for if corr-reports have a space before ever line in them (e.g. aov032)
                corr_section = contents.split('\n +')
        relevant_section = extractRelevantSections(corr_section)
        if len(relevant_section) < 4:
            return print("Incompatible correlator report format.")
        station_id = ["Ke", "Yg", "Hb", "Ho"]
        # Extract manual pcal and dropped channels for all telescopes first
        dropped_channels = droppedChannels(relevant_section[1])
        manual_pcal = manualPcal(relevant_section[2])
        # Now to extract what we need to calculate the SEFDs
        if os.path.isfile(os.getcwd()+'/skd_files/' + str(exp_id) + '.skd'):
            with open(os.getcwd()+'/skd_files/' + str(exp_id) + '.skd') as file:
                skd_contents = file.read()
            antennas_corr_reference = antennaReference_CORR(relevant_section[0])
            if len(antennas_corr_reference) == 0:
                return print("No stations defined in correlator report!")
            antenna_reference = antennaReference_SKD(skd_contents)
            snr_data, corrtab_X, corrtab_S = sefdTableExtract(relevant_section[3], antennas_corr_reference, antenna_reference)
            if len(snr_data) == 0: # this is if corr file exists, but no SNR table exists.
                print("No SNR table exists!")
                for j in range(0, len(station_id)):
                    sql_station = """
                        UPDATE {} 
                        SET Manual_Pcal=%s, Dropped_Chans=%s 
                        WHERE ExpID=%s
                    """.format(station_id[j])
                    data = [manual_pcal[j], dropped_channels[j], str(exp_id)]
                    conn = mariadb.connect(user='auscope', passwd='password', db=str(db_name))
                    cursor = conn.cursor()
                    cursor.execute(sql_station, data)
                    conn.commit()
                    conn.close()
            else:
                SEFD_tags, SEFD_X, SEFD_S = predictedSEFDextract(skd_contents, antenna_reference)
                basnum = basnumArray(snr_data, antennas_corr_reference, SEFD_tags)
                print("Calculating SEFD values for experiment " + exp_id + ".")
                X = SEFD_estimator.main(SEFD_X, corrtab_X, basnum)
                S = SEFD_estimator.main(SEFD_S, corrtab_S, basnum)
                for i in range(0, len(station_id)):
                    if len(X) == 1 or len(S) == 1: # For the case where there are less than 3 stations with valid data
                        print("Less than 3 stations, adding only manual pcal and dropped channel data.")
                        sql_station = """
                            UPDATE {} 
                            SET Manual_Pcal=%s, Dropped_Chans=%s 
                            WHERE ExpID=%s
                        """.format(station_id[i])
                        data = [manual_pcal[i], dropped_channels[i], str(exp_id)]
                        conn = mariadb.connect(user='auscope', passwd='password', db=str(db_name))
                        cursor = conn.cursor()
                        cursor.execute(sql_station, data)
                        conn.commit()
                        conn.close()
                    elif station_id[i] in SEFD_tags:
                        sql_station = """
                            UPDATE {}
                            SET estSEFD_X=%s, estSEFD_S=%s, Manual_Pcal=%s, Dropped_Chans=%s
                            WHERE ExpID=%s
                        """.format(station_id[i])
                        data = [round(X[list(SEFD_tags).index(station_id[i])],2), round(S[list(SEFD_tags).index(station_id[i])],2), manual_pcal[i], dropped_channels[i], str(exp_id)]
                        conn = mariadb.connect(user='auscope', passwd='password', db=str(db_name))
                        cursor = conn.cursor()
                        cursor.execute(sql_station, data)
                        conn.commit()
                        conn.close()                    
        else: ### this sql command is for if no SKD file is present and hence no calculation is possible.
            print("No SKD file is available!")
            for j in range(0, len(station_id)):
                sql_station = """
                    UPDATE {} 
                    SET Manual_Pcal=%s, Dropped_Chans=%s 
                    WHERE ExpID=%s
                """.format(station_id[j])
                data = [manual_pcal[j], dropped_channels[j], str(exp_id)]
                conn = mariadb.connect(user='auscope', passwd='password', db=str(db_name))
                cursor = conn.cursor()
                cursor.execute(sql_station, data)
                conn.commit()
                conn.close()
        

    

if __name__ == '__main__':
    # analysis_downloader.py executed as a script
    main(sys.argv[1], sys.argv[2])
