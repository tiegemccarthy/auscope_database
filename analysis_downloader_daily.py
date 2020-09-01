#!/usr/bin/python

from ftplib import FTP
import ftplib
import re
import os
import MySQLdb as mariadb
import sys
import tarfile

dirname = os.path.dirname(__file__)
#
#

def checkExistingData(db_name):
    # db_name should be the name of the auscope database (as a string) we want to query for 
    #  unique existing experiment IDs
    conn = mariadb.connect(user='auscope', passwd='password', db=db_name)
    cursor = conn.cursor()
    station_key = ['Ke', 'Yg', 'Hb', 'Ho']
    existing_experiments = []

    for ant in station_key:
        query = "SELECT ExpID FROM " + ant
        cursor.execute(query)
        result_list = [item for sublist in cursor.fetchall() for item in sublist]
        existing_experiments.append(result_list)
    
    existing_experiments = [item for sublist in existing_experiments for item in sublist]
    unique_existing_experiments = set(existing_experiments)
    return unique_existing_experiments

def validExpFinder(master_schedule):
    schedule = str(master_schedule)
    with open(schedule) as file:
        schedule_contents = file.readlines()
    valid_experiment = []
    for line in schedule_contents:
        line = line.split('|')
        if len(line) > 13 and '1.0' in line[11]:
            regex = '(?<!-)Ke|(?<!-)Yg|(?<!-)Hb|(?<!-)Ho'
            participated = re.findall(regex,line[7],re.MULTILINE)
            if len(participated) > 0:
                valid_experiment.append(line[2].strip())
    return valid_experiment


def corrReportDL(exp_id,vgos_tag):
    year = '20' + str(vgos_tag[0:2])
    tag = str(vgos_tag.rstrip())
    exp_id = str(exp_id)
    vgos_exists = []
    if os.path.isfile(dirname+"/corr_files/"+ exp_id + '.corr'):
        print("Corr report already exists for experiment " + exp_id + ", skipping re-download.")
        return
    else:
        ftp = FTP('ivs.bkg.bund.de')
        ftp.login()
        try:
            ftp.retrlines("LIST /pub/vlbi/ivsdata/vgosdb/" + year + "/" + tag + ".tgz", vgos_exists.append)
            if len(vgos_exists) > 0:
                local_filename = os.path.join(dirname, tag + ".tgz")
                lf = open(local_filename, "wb")
                ftp.retrbinary("RETR /pub/vlbi/ivsdata/vgosdb/" + year + "/" + tag + ".tgz", lf.write)
                lf.close()
                tar = tarfile.open(dirname + '/' + tag + ".tgz")
                if tag +'/History/'+ tag + '_V000_kMk4.hist' in tar.getnames():
                    member = tar.getmember(tag +'/History/'+ tag + '_V000_kMk4.hist')
                    member.name = dirname + '/corr_files/' + exp_id + '.corr'
                    tar.extract(member)
                    tar.close()
                else:
                    file_list = tar.getnames()
                    regex = re.compile('.*V...\.hist')
                    for file in file_list:
                        if re.match(regex,file):
                            member = tar.getmember(file)
                            member.name = dirname + '/corr_files/' + exp_id + '.corr'
                            tar.extract(member)
                            tar.close()
                            break
                os.remove(dirname + '/' + tag + ".tgz")
                print("Corr report download complete for experiment " + exp_id + ".")
                return 
        except Exception:
            print("Corr report not available for experiment " + exp_id + ".")
            return
    



    
def main(master_schedule, db_name):
    schedule = str(master_schedule)
    ftp = FTP('ivs.bkg.bund.de')
    ftp.login()
    master_sched_filename = os.path.join(dirname, schedule)
    mf = open(master_sched_filename, "wb")
    ftp.retrbinary('RETR /pub/vlbi/ivscontrol/'+ schedule, mf.write)
    mf.close()

    valid_experiment = validExpFinder(os.path.join(dirname, schedule))
    existing_experiments = checkExistingData(str(db_name))
    if existing_experiments == None:
        experiments_to_download = valid_experiment
    else:
        experiments_to_download = [x for x in valid_experiment if x not in existing_experiments]
    year = '20' + schedule[6:8]
    for exp in experiments_to_download:
        if os.path.isfile(dirname+'/analysis_reports/'+exp.lower()+'_report.txt'):
            print("Analysis report already exists for " + exp.lower() + ", skipping file downloads.")
            continue
        else:
            #ftp = FTP('cddis.gsfc.nasa.gov')
            exp = exp.lower()
            print('Beginning file downloads for experiment ' + exp + ".")
            ftp = FTP('ivs.bkg.bund.de')
            ftp.login()
            # Download SKED file
            try:
                filename_skd = []
                ftp.retrlines('LIST /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + '.skd', filename_skd.append)
                if len(filename_skd) > 0:
                    local_filename_skd = os.path.join(dirname, 'skd_files/' + exp + '.skd')
                    lf3 = open(local_filename_skd, "wb")
                    ftp.retrbinary('RETR /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + ".skd", lf3.write)
                    lf3.close()
            except Exception: 
                print('No SKED file found for ' + exp)
            
            # Spelling options need to be here because analysis report names are unfortunately not standardised - sometimes they are even different within the same experiment (e.g. 'ivs' and 'IVS')
            # Now time to download analysis report
            options = ['ivs', 'IVS', 'usno', 'USNO', 'NASA']
            for spelling in options:
                filename_report = []
                try:
                    ftp.retrlines('LIST /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + '-'+spelling+'-analysis-report*', filename_report.append)
                    if len(filename_report) > 0:
                        local_filename_report = os.path.join(dirname, 'analysis_reports/' + exp + '_report.txt')
                        lf1 = open(local_filename_report, "wb")
                        ftp.retrbinary('RETR ' + filename_report[len(filename_report)-1].split()[8], lf1.write)
                        lf1.close()
                        print('Analysis report downloaded for experiment ' + exp + ".")
                        break
                except Exception:
                    pass
            # Download spool file
            for spelling in options:
                filename_spool = []
                try:
                    ftp.retrlines('LIST /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + '-'+spelling+'-analysis-spoolfile*', filename_spool.append)
                    if len(filename_spool) > 0:
                        local_filename_spool = os.path.join(dirname, 'analysis_reports/' + exp + '_spoolfile.txt')
                        lf2 = open(local_filename_spool, "wb")
                        ftp.retrbinary('RETR ' + filename_spool[len(filename_report)-1].split()[8], lf2.write)
                        lf2.close()
                        print('Spoolfile downloaded for experiment ' + exp + ".")
                        break
                except Exception:
                    pass
            # Download old style analysis report if it exists.
            try:
                filename_report_old = []
                ftp.retrlines('LIST /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + '-analyst.txt', filename_report_old.append)
                if len(filename_report_old) > 0:
                    local_filename_report = os.path.join(dirname, 'analysis_reports/' + exp + '_report.txt')
                    lf1 = open(local_filename_report, "wb")
                    ftp.retrbinary('RETR /pub/vlbi/ivsdata/aux/'+str(year)+ '/' + exp + '/' + exp + "-analyst.txt", lf1.write)
                    lf1.close()
            except Exception:
                    pass   


if __name__ == '__main__':
    # auscope_file_scraper.py executed as a script
    main(sys.argv[1], sys.argv[2])
    

