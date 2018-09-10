import csv
import sys
import requests
import json
import psycopg2

# User fed parameters
file="MIMIC_NOTEEVENTS.csv"
solr_url="<Enter Solr URL here>"
conn_string = "host='%s' dbname='%s' user='%s' password='%s' port=%s" % ('host',
                                                                             'dbname',
                                                                             'user',
                                                                             'password',
                                                                             'port')

# Constructing solr_url
url = solr_url + '/update?commit=true'
headers = {
'Content-type': 'application/json',
}

# Connecting to the database
conn = psycopg2.connect(conn_string)
cursor = conn.cursor()

# to keep track of the number of rows which have been passed
count = 0

# Keeping track of chunk statistics
chunk = 0
chunk_size = 10000
num_chunk_failed = 0

# Extracting person_source_value -> person_id mapping information from the database
cursor.execute("""SELECT person_id, person_source_value from mimic_v5.person;""")
result = cursor.fetchall()
map = dict()
for i in result:
    pid = i[0]
    psv = i[1]
    if psv not in map:
        map[psv] = pid

# Pushing data to Solr
try:
    # read in large csv file
    csvfile = open(file, 'r')
    reader = csv.DictReader(csvfile)
    # Uploading file in chunks to server
    s = []
    for row in reader:

        # Getting the person_source_value to person_id mapping
        subject_id = map[row['SUBJECT_ID']]

        d = {'subject': subject_id,
            'description_attr': row['DESCRIPTION'],
            'source': 'MIMIC',
            'report_type': row['CATEGORY'],
            'report_text': row['TEXT'],
            'cg_id': row['CGID'],
            'report_id': row['ROW_ID'],
            'is_error_attr': row['ISERROR'],
            'id': row['ROW_ID'],
            'store_time_attr': row['STORETIME'],
            'chart_time_attr': row['CHARTTIME'],
            'admission_id': row['HADM_ID'],
            'report_date': row['CHARTDATE']
            }
        s.append(d)

        # Chunking
        count += 1
        if count == chunk_size:
            data = json.dumps(s)
            response = requests.post(url, headers=headers, data=data)
            chunk += 1
            print ("\n\nChunk " + str(chunk) + " " + str(response.status_code))
            if response.status_code != 200:
                num_chunk_failed += 1
            s.clear()
            count = 0

    # Upload any remnant rows
    if len(s) > 0:
        response = requests.post(url, headers=headers, data=data)
        chunk += 1
        print ("\n\nChunk " + str(chunk) + " " + str(response.status_code))
        if response.status_code != 200:
            num_chunk_failed += 1

    # Close file connection
    csvfile.close()

    # Printing statistics
    print ("\n\nFINAL STATISTICS\n")
    print ("\nChunk size = " + str(chunk_size))
    print ("\nNumber of chunks = " + str(chunk))
    print ("\nNumber of failed chunk uploads = " + str(num_chunk_failed))
    print("\n\n")

except Exception as ex:
    print ("\n")
    print (ex)
    print ("\n")
