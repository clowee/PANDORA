import requests
import math
from datetime import datetime, timedelta
from pathlib import Path
import sys
import pandas as pd

SERVER = "https://sonarcloud.io/"
ORGANIZATION = "apache"

def query_server(type, iter = 1, project_key = None, metric_list = []):

    page_size = 200
    params = {'p' : iter, 'ps':page_size}
    if type == 'projects':
        endpoint = SERVER + "api/components/search"
        params['organization'] = ORGANIZATION
        params['qualifiers'] = 'TRK'

    elif type == 'metrics':
        endpoint = SERVER + "api/metrics/search"

    elif type == 'analyses':
        endpoint = SERVER + "api/project_analyses/search"
        params['project'] = project_key

    elif type == 'measures':
        endpoint = SERVER + "api/measures/search_history"
        params['component'] = project_key
        params['metrics'] = ','.join(metric_list)

    else:
        print("ERROR: Illegal info type.")
        return None

    r = requests.get(endpoint, params=params)

    if r.status_code != 200:
        print(f"ERROR: HTTP Response code {r.status_code} for request {r.request.path_url}")
        return None

    r_dict = r.json()

    if type == 'projects':
        element_list = r_dict['components']
        total_num_elements = r_dict['paging']['total']
    elif type == 'metrics':
        element_list = r_dict['metrics']
        total_num_elements = r_dict['total']
    elif type == 'analyses':
        element_list = r_dict['analyses']
        total_num_elements = r_dict['paging']['total']
    elif type == 'measures':
        element_list = r_dict['measures']
        total_num_elements = r_dict['paging']['total']

    if iter*page_size < total_num_elements:
        if type == 'measures':
            element_list = concat_measures(element_list, query_server(type, iter+1, project_key))
        else:
            element_list = element_list + query_server(type, iter+1, project_key)
    
    return element_list

def concat_measures(measures_1,measures_2):
    for measure_1, measure_2 in zip(measures_1, measures_2):
        measure_1['history'] = measure_1['history'] + measure_2['history']
    return measures_1


def process_datetime(time_str):
    if time_str is None:
        return None

    ts = datetime.strptime(time_str[:19], "%Y-%m-%dT%H:%M:%S")

    offset = timedelta(hours = int(time_str[20:22]), minutes = int(time_str[22:24]))

    if time_str[19] == '-':
        ts = ts + offset
    elif time_str[19] == '+':
        ts = ts - offset
    
    return ts

def load_metrics(path = None):
    if path is None:
        path = './all_metrics.txt'
    p = Path(path)
    if not p.exists():
        print(f"ERROR: Path for metrics {p.resolve()} does not exists.")
        sys.exit(1)
    try:
        metrics_list = []
        with open(p, 'r') as f:
            for line in f:
                metrics_list.append(line.split(' - ')[2])
        return metrics_list
    except:
        print("ERROR: Reading metrics file")
        sys.exit(1)

def extract_measures_value(measures):
    columns = []
    data = {}
    for measure in measures:
        metric = measure['metric']
        columns.append(metric)
        history = measure['history']
        values = list((map(lambda x: None if 'value' not in x else x['value'], history)))
        data[metric] = values
    
    return columns, data

def process_project(project, metrics_path = None):

    project_key = project['key']
    project_analyses = query_server('analyses', 1, project_key = project_key)

    revision_list = []
    date_list = []
    version_list = []
    for analysis in project_analyses:
        revision = None if 'revision' not in analysis else analysis['revision']
        revision_list.append(revision)
        date = None if 'date' not in analysis else process_datetime(analysis['date'])
        date_list.append(date)
        version = None if 'projectVersion' not in analysis else analysis['projectVersion']
        version_list.append(version)
    
    metrics = load_metrics(metrics_path)

    measures = []
    for i in range(0,len(metrics), 15):
        #Get measures
        measures = measures + query_server('measures',1,project_key, metrics[i:i+15])

    # For testing
    # return measures

    metric_columns, measures_data = extract_measures_value(measures)
    #Create DF
    df = pd.DataFrame(measures_data, metric_columns)


if __name__ == "__main__":

    # metric_list = query_server(type='metrics')
    # metric_list.sort(key = lambda x: ('None' if 'domain' not in x else x['domain'], int(x['id'])))

    # # Write all metrics to a file
    # with open('./all_metrics.txt', 'w') as f:
    #     for metric in metric_list:
    #         f.write("{} - {} - {} - {}\n".format(
    #             'No ID' if 'id' not in metric else metric['id'],
    #             'No Domain' if 'domain' not in metric else metric['domain'],
    #             'No Key' if 'key' not in metric else metric['key'],
    #             'No Description' if 'description' not in metric else metric['description']
    #             ))


    project_list = query_server(type='projects')
    project_list.sort(key = lambda x: x['key'])

    for project in project_list:
        process_project(project)