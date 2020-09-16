#!/bin/bash

# pull current date in an appropriate format.
now=`date +"%Y-%m-%d"`
# make weekly logs directory if it does not exist.
mkdir -p weekly_logs
# copy current weekly log to the weekly logs directory.
cp ~/auscope_db/current.log ~/auscope_db/weekly_logs/${now}.log
# email current log - fill in email adress and double check path to log.
mail -s "AuScopeDB weekly log - ${now}" <email_address> < ~/auscope_db/weekly_logs/${now}.log
# remove current log file ready for new week
rm ~/auscope_db/current.log
