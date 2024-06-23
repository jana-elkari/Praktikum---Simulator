import bottle
import json
import random
import sqlite3
import requests
import time
import numpy as np
from datetime import datetime
import threading
import operator
from bottle import request
# Patient generator
patienttypes = ["ER", "A", "B"]
#a_diagnosis= ["A1", "A1", "A1", "A1", "A2", "A2", "A3", "A4", "B1", "B1", "B1", "B1", "B2", "B2", "B3", "B4", "ER"]
#the above one is correct, the below one is wrong BUT I wanted more ER patients to be generated for testing
a_diagnosis= ["ER", "ER", "ER", "ER", "ER", "ER", "A3", "A4", "B1", "B1", "B1", "B1", "B2", "B2", "B3", "B4", "ER"]
for i in range(5):
    patienttype = random.choice(a_diagnosis)
    response = requests.post(
        "https://cpee.org/flow/start/url/",
        data={"behavior": "fork_running", "url": "https://cpee.org/hub/server/Teaching.dir/Prak.dir/Challengers.dir/ElKari_Jana.dir/Main.xml",
              "init": json.dumps({"patienttype": patienttype})}
    )

    if response.status_code == 200:
        print("Response successful ", response.text)
    else:
        print("Request failed")
original_arrival= None
diagnosis = ''
er = None
#diagnosis2 = ''
@bottle.route('/generate')
def generate():
    arguments = dict(request.query.items())
#print(arguments)
    patienttype = arguments.get('type')
    #patienttype = 'ER'
    #print('HON')
    print(patienttype)
    original_arrival = datetime.now().isoformat()    
    print(original_arrival)
    connection = sqlite3.connect('resources.db')
    cursor = connection.cursor()
    cursor.execute("SELECT Count FROM resources")
    counts = cursor.fetchall()
    connection.close()
    #diagnosis = random.choice(a_diagnosis)
    #print('diagnosis')
    #print(patienttype)
    if (patienttype =='A1' or patienttype =='B1' or patienttype =='B2'):
        surgery = False
        er = False
    elif (patienttype == 'ER'):
        surgery = True
        er = True
    else:
        surgery = True
        er = False
    #checkingdatabase = 
    patientdata = {
        'patienttype': patienttype,
        'complications': random.choice([True, False]),
        'phantompain': random.choice([False, False]),
        'ertreatment': True,
        #'surgery': random.choice([True, False]),
        'resources': random.choice([True, True,False]),
        #'timeofarrival': original_arrival
        'surgery': surgery,
        'nursing': True #all types of diagnosis need nursing
    }
    #print(surgery)
    #print(er)
    return bottle.HTTPResponse(
        json.dumps(patientdata),
        status=200,
        headers={'Content-Type': 'application/json'}
    )
tim = None
#this is a dumb simulator, re-shedules everyone to the next day
@bottle.route('/replan')
def replan():
    arguments = dict(request.query.items())
    print(arguments)
    id = arguments.get('id')
    r = arguments.get('resources')
    tim = arguments.get('originalarrival')
    typee = arguments.get('patienttype')
    datanew = {
        "behavior": "fork_running",
        "url": "https://cpee.org/hub/server/Teaching.dir/Prak.dir/Challengers.dir/ElKari_Jana.dir/Main.xml",
        "init": json.dumps({
            "patienttype": typee, 
            "status": "oldpatient", 
            'complications': random.choice([True, False]),
            'phantompain': random.choice([True, False]),
            'ertreatment': random.choice([True, False]),
            'surgery': random.choice([True, False]),
            'patient_id': id,
            'original': tim,
            'resources': r
        })
    }
    time.sleep(20)
    print('please come back in 20 seconds (nextday), we will keep your original arrival time saved')
    response = requests.post("https://cpee.org/flow/start/url/", data=datanew)
    print("Patient replanned:", response.text)

queue = []
queue2 = []
lock = threading.Lock()

def process_queue():
    connection = sqlite3.connect('resources.db')
    cursor = connection.cursor()

    with lock:
        while queue:
            cursor.execute("SELECT count FROM resources WHERE role = 'ER Personal'")
            counter = cursor.fetchone()[0]
            if counter > 0:
                patient = queue.pop(0)
                url = patient['callback_id']
                cursor.execute("UPDATE resources SET count = count - 1 WHERE role = 'ER Personal'")
                connection.commit()
                print(f"Processing ER queue for patient {patient['patient_id']}")
                requests.put(url, headers={'CPEE-CALLBACK': 'true'})
                time.sleep(10)  # Simulate resource usage time
                cursor.execute("UPDATE resources SET count = count + 1 WHERE role = 'ER Personal'")
                connection.commit()
                print(f"Finished processing ER patient {patient['patient_id']}")
            else:
                break

        while queue2:
            cursor.execute("SELECT count FROM resources WHERE role = 'Intake Personal'")
            counter2 = cursor.fetchone()[0]
            if counter2 > 0:
                patient = queue2.pop(0)
                url = patient['callback_id']
                cursor.execute("UPDATE resources SET count = count - 1 WHERE role = 'Intake Personal'")
                connection.commit()
                print(f"Processing Intake queue for patient {patient['patient_id']}")
                requests.put(url, headers={'CPEE-CALLBACK': 'true'})
                time.sleep(10)  # Simulate resource usage time
                cursor.execute("UPDATE resources SET count = count + 1 WHERE role = 'Intake Personal'")
                connection.commit()
                print(f"Finished processing inatke patient {patient['patient_id']}")
            else:
                break

    connection.close()

def sortfxn(queue):
    queue.sort(key=operator.itemgetter('original_arrival_time'))
    return queue

@bottle.route('/simulator')
def simulator():
    arguments2 = dict(request.query.items())
    print(arguments2)
    id = arguments2.get('id')
    task = arguments2.get('task')
    arrival = arguments2.get('arrival')
    #duration = int(arguments2.get('duration'))
    duration = np.abs(np.random.normal(loc=0, scale=1))
    print('This is the duration of the task')
    print(duration)
    connection = sqlite3.connect('resources.db')
    cursor = connection.cursor()

    if (task == 'er'):
        with lock:
            cursor.execute("SELECT count FROM resources WHERE role = 'ER Personal'")
            counter = cursor.fetchone()[0]

        if (counter > 0):
            cursor.execute("UPDATE resources SET count = count - 1 WHERE role = 'ER Personal'")
            connection.commit()
            print('ER patient is admitted')
            threading.Thread(target=release_patient, args=(id, task, duration)).start()
        else:
            url = bottle.request.headers['Cpee-Callback']
            print("CallBack-url")
            print(url)
            queue.append({'patient_id': id, 'callback_id': url, 'original_arrival_time': arrival})
            print("er queue before sorting")
            print(queue)
            sortfxn(queue)
            print("er queue after sorting")
            print(queue)
            print('ER patient is rescheduled')
            return bottle.HTTPResponse(headers={'content-type': 'application/json', 'CPEE-CALLBACK': 'true'})

    elif (task == 'intake'):
        with lock:
            cursor.execute("SELECT count FROM resources WHERE role = 'Intake Personal'")
            counter2 = cursor.fetchone()[0]                

        if (counter2 > 0):
            cursor.execute("UPDATE resources SET count = count - 1 WHERE role = 'Intake Personal'")
            connection.commit()
            print('Intake patient is admitted')
            threading.Thread(target=release_patient, args=(id, task, duration)).start()
        else:
            url = bottle.request.headers['Cpee-Callback']
            print("No resources. Callback url where we should send put request when resources are available")
            print(url) 
            queue2.append({'patient_id': id, 'callback_id': url ,'original_arrival_time': arrival})
            print("intake queue before sorting")
            print(queue2)
            sortfxn(queue2)
            print('intake queue after sorting')
            print(queue2)
            print('Intake patient is rescheduled')
            return bottle.HTTPResponse(status=200, headers={'content-type': 'application/json', 'CPEE-CALLBACK': 'true'})
    elif (task == 'release'):
        print('THE PATIENT IS RELEASED FORM THE HOSPITAL!')
    
    connection.close()
#no need to pass anything related to the resources, we use sqlite database
def release_patient(id, task, duration):
    connection = sqlite3.connect('resources.db')
    cursor = connection.cursor()
    
    time.sleep(duration)

    if (task == 'er'):
        with lock:
            cursor.execute("UPDATE resources SET count = count + 1 WHERE role = 'ER Personal'")
            connection.commit()
        print('ER patient is discharged after duration')
    elif (task == 'intake'):
        with lock:
            cursor.execute("UPDATE resources SET count = count + 1 WHERE role = 'Intake Personal'")
            connection.commit()
        print('Intake patient is discharged after duration')
    


    connection.close()

    process_queue()

def main():
    bottle.run(host='::0', port=7773)

main()
