#!/usr/bin/python

import re
import os
import MySQLdb as mariadb
import auscope_file_scraper
import analysis_downloader_daily
import corr_skd_ingest
import sys
import csv

dirname = os.path.dirname(__file__)
   
def main(master_schedule, db_name):
    # CREATE DATABASE IF REQUIRED
    master_schedule = str(master_schedule)
    db_name = str(db_name) 
    station_id = ['Ke', 'Yg', 'Hb', 'Ho']
    conn = mariadb.connect(user='auscope', passwd='password')
    cursor = conn.cursor()
    query = "CREATE DATABASE IF NOT EXISTS " + db_name +";"
    cursor.execute(query)
    conn.commit()
    query = "USE " + db_name
    cursor.execute(query)
    conn.commit()
    for ant in station_id:
        query = "CREATE TABLE IF NOT EXISTS "+ ant + " (ExpID VARCHAR(10) NOT NULL PRIMARY KEY, Performance decimal(4,3) NOT NULL, Date DATETIME , Date_MJD decimal(9,2), Pos_X decimal(14,2), Pos_Y decimal(14,2), Pos_Z decimal(14,2), Pos_U decimal(14,2), Pos_E decimal(14,2), Pos_N decimal(14,2), W_RMS_del decimal(5,2), estSEFD_X decimal(8,2), estSEFD_S decimal(8,2), Manual_Pcal BIT(1), Dropped_Chans VARCHAR(150), Problem BIT(1), Problem_String VARCHAR(100), Analyser VARCHAR(10) NOT NULL, vgosDB_tag VARCHAR(10));" 
        cursor.execute(query)
        conn.commit()
    conn.close()
    # Create CSV files for analysis reports and SEFD
    for ant in station_id:
        # analy reports
        if os.path.isfile(dirname+'/' + ant + '_analysis_reports.csv'):
            continue
        else:
            with open(ant + '_analysis_reports.csv','a') as f:
                station_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                station_writer.writerow(['ExpID', 'Performance', 'Date', 'Date_MJD', 'Pos_X', 'Pos_Y', 'Pos_Z', 'Pos_U', 'Pos_E', 'Pos_N', 'W_RMS_del', 'Problem', 'Problem_String', 'Analyser', 'vgosDB_tag']) 
        # corr reports
        if os.path.isfile(dirname+'/' + ant + '_corr_reports.csv'):
            continue
        else:
            with open(ant + '_corr_reports.csv','a') as f:
                station_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                station_writer.writerow(['estSEFD_X', 'estSEFD_S', 'Manual_Pcal', 'Dropped_Chans', 'ExpID']) 
    # DOWNLOAD ANY SKD/ANALYSIS/SPOOL FILES THAT ARE IN THE MASTER SCHED, BUT NOT IN DATABASE YET. 
    analysis_downloader_daily.main(master_schedule, db_name) # comment this line out for troubleshooting downstream problems, otherwise this tries to redownload all the experiments with no files available.
    # SCRAPE FILES THAT ARENT IN THE DATABASE
    valid_experiments = analysis_downloader_daily.validExpFinder(os.path.join(dirname, master_schedule))
    existing_experiments = analysis_downloader_daily.checkExistingData(str(db_name))
    #experiments_to_add = [x for x in valid_experiments if x not in existing_experiments]
    experiments_to_add = valid_experiments
    for exp in experiments_to_add:
        exp = exp.lower()
        if os.path.isfile(dirname+'/analysis_reports/'+ exp +'_report.txt'):
            auscope_file_scraper.main(exp, db_name)
            with open(dirname + '/analysis_reports/'+ exp +'_report.txt') as file:
                meta_data = auscope_file_scraper.metaData(file.read())
            vgosDB = meta_data[4]
            analysis_downloader_daily.corrReportDL(exp, vgosDB)
            corr_skd_ingest.main(exp, db_name)
                
   
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])




