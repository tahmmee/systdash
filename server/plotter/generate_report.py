from optparse import OptionParser
import sys
sys.path.append(".")
import datetime
import pandas as pd
import pygal
from pygal.style import RedBlueStyle
import os
import shutil
from seriesly import Seriesly, exceptions
import requests
import zipfile
import tarfile 
import json 
import gzip 
from final_report import FinalReport

archives = []
HighDeviationMap = {}
CBFS_HOST = 'http://cbfs.hq.couchbase.com:8484'



def pullStats(path):
  baseline_path = None
  path = os.path.split(path)[0]
  r=requests.get('%s/.cbfs/list/%s' % (CBFS_HOST, path))
  response = r.json()

  if 'dirs' in response:
    if 'baseline' in response['dirs']:
      baseline_path = '%s/baseline/' % path

      # retrieve from cbfs and unpack locally
      f = open('baseline.zip', 'wb')
      r=requests.get('%s/.cbfs/zip/%s' % (CBFS_HOST, baseline_path))
      f.write(r.content)
      f.close()
      zf = zipfile.ZipFile('baseline.zip')
      zf.extractall()


  return baseline_path

def generateGraphs(baseline, comparisons):

  report = FinalReport(baseline, comparisons)
  local_path = report.local_path
  max_frames = 1000

  for bucket in baseline.buckets:


    baseline_path = "%s/%s" % (baseline.path_full, bucket)
    baseline_files =  os.listdir(baseline_path)
    for base_phase in baseline_files:
      suffix = base_phase.split('.')[-1]
      cmp_dataframes = []
      hideviations =  []
      skip_frames = 1

      if suffix == 'csv':
        phase_no = int(base_phase.split('.')[-2].split('phase')[1])
        base_dataframe =  pd.read_csv('%s/%s' % (baseline_path, base_phase))
        if len(base_dataframe) == 0:
          continue

        base_interval = phaseTime(base_dataframe)

        if(len(base_dataframe) > 100):
          skip_frames = len(base_dataframe)/100
          base_dataframe  = base_dataframe[::skip_frames]

        # look for similar file in compare paths
        for comparison in comparisons:
          compare_path = "%s/%s" % (comparison.path_full, bucket)

          cmp_files =  os.listdir(compare_path)
          for cmp_phase in cmp_files:
            if cmp_phase == base_phase:
              df =  pd.read_csv('%s/%s' % (compare_path, cmp_phase))[::skip_frames]
              df.build_title = comparison.title
              if len(df) > 0:
                cmp_dataframes.append(df)
              break

         
        phase_html = ("%s/%s/%s" % (local_path, bucket, base_phase.replace(suffix,'html')))
        f = open(phase_html,"w")
        print "writing %s" % phase_html


        for column in base_dataframe.columns[1:]:
        # try:
          # filter out no-data columns
          if all([v == 0 for v in base_dataframe[column].values]):
            continue

          # filter out all-nan columns
          if any(v == True for v in pd.isnull(base_dataframe[column])):
            if all(v == True for v in pd.isnull(base_dataframe[column])):
              continue
            else:
              base_dataframe[column] = map(lambda v:  (v, 0)[pd.isnull(v)] , base_dataframe[column])


          # write to Line chart
          chart = initLineChart(base_dataframe, column)
          chart.add(baseline.title, [round(v,2) for v in base_dataframe[column].values] )
          for cmp_dataframe in cmp_dataframes:
            if column in cmp_dataframe:
              chart.add(comparison.title, [round(v,2) for v in cmp_dataframe[column].values] )
          renderToFile(chart, column, f)

          # write to bar chart
          chart = initBarChart(base_dataframe, column)
          vals = base_dataframe[column].describe().values[1:] 
          vals = map(lambda v:  (round(v,2), 0)[pd.isnull(v)] , vals)
          chart.add("baseline", vals)

          for cmp_dataframe in cmp_dataframes:
            if column not in cmp_dataframe:
              continue

            perc_diff, perc_val = getPercDiff(base_dataframe, cmp_dataframe, column)
            vals = cmp_dataframe[column].describe().values[1:] 
            vals = map(lambda v:  (round(v,2), 0)[pd.isnull(v)] , vals)
            chart.add(str(perc_diff), vals)

            # record high perc_diffs
            if(abs(perc_val) > 20):
              print "Phase %s: detected %s change in %s" % (base_phase, perc_val, column)
              hideviations.append({column : {'diff' : perc_diff, 'build' : cmp_dataframe.build_title}})

          renderToFile(chart, column, f)
        #except Exception as ex:
        #  import pdb; pdb.set_trace()
        #  x=22

        # check phase intervals
        #try:
        if len(cmp_dataframes) > 0:
          cmp_interval = phaseTime(cmp_dataframe)
          time_diff = cmp_interval - base_interval
          if (abs(time_diff)) > 60:
            if(time_diff) > 0:
              time_diff = "+"+str(time_diff)

            time_diff = str(time_diff)+"s"
            print "Phase %s: detected %s change in %s" % (base_phase, time_diff, 'phase_time')
            hideviations.append({'phase_time' : {'diff' : time_diff, 'build' : cmp_dataframe.build_title}})

        report.addPhase(base_phase.replace('csv','html'), phase_no, phase_html, hideviations, bucket)
       #except Exception as ex:
       #  import pdb; pdb.set_trace()
       #  x=100
        f.close()

  final_report = "%s/%s" % (local_path, report.name)
  print "writing %s" % final_report 
  f = open(final_report, "wb")
  f.write(report.render())
  f.close()

  return report

def getPercDiff(base_dataframe, cmp_dataframe, column):
    base_median = base_dataframe[column][base_dataframe[column] > 0].median()
    cmp_median = cmp_dataframe[column][cmp_dataframe[column] > 0].median()
    perc_change = 0


    if cmp_median <= 0:
      perc_change = -100 
    else:
      perc_change = round((cmp_median - base_median)/float(base_median),3)*100

    perc_change_str = str(perc_change)+"%"

    if perc_change > 0:
      perc_change_str = "+"+perc_change_str

    return perc_change_str, perc_change


def renderToFile(chart, name, f):

  # write out chart html
  #res = chart.render_response()
  f.write('<a name="%s">' % name)
  f.write(chart.render())
  f.write('</a>')


def initBarChart(base_dataframe, column = 'default'):

  # present mean/std/etc.. stats as bar chart
  chart=pygal.Bar(title = column,
                  show_dots = False,
                  print_values=False,
                  print_zeros=False,
                  human_readable=True,
                  #legend_at_bottom = True,
                  style=RedBlueStyle)

  chart.x_labels = ['mean', 'std', 'min', '25%', '50%', '75%', 'max']

  #vals = base_dataframe[column].describe().values[1:]
  vals = base_dataframe[column][base_dataframe[column] > 0].describe()[1:] 
  vals = map(lambda v:  (v, 0)[pd.isnull(v)] , vals)
    
  return chart

def phaseTime(dataframe):
  ts_column = dataframe.columns[0]
  timestamps = dataframe[ts_column].values
  start_date = tsToDate(timestamps[0])
  end_date = tsToDate(timestamps[-1]) 
  interval = end_date - start_date
  return interval.seconds

def tsToDate(ts):
  return datetime.datetime.strptime(ts[:ts.index('.')],"%Y-%m-%dT%H:%M:%S")

def initLineChart(dataframe, title = 'default'):

  # plot phase data and filter 0's values
  chart=pygal.Line(title = title,
                   fill=False,
                   show_dots = False,
                   print_values=False,
                   print_zeros=False,
                   human_readable=True,
                   style=RedBlueStyle)
  chart.truncate_label = 10


  # only display '5' timestamps (x_timestamp_cnt)
  ts_column = dataframe.columns[0]
  timestamps = dataframe[ts_column].values
  x_timestamp_cnt = 5
  x_step = len(timestamps)/x_timestamp_cnt or 1
  x_indexes_to_plot = range(0, len(timestamps), x_step)
  chart.x_labels = []
  init_ts = timestamps[0]
  curr_day = datetime.datetime.strptime(init_ts[:init_ts.index('.')],"%Y-%m-%dT%H:%M:%S").day

  for ts in timestamps:

    if(timestamps.tolist().index(ts) in x_indexes_to_plot):
      # display hour/min/sec format
      ts_date = datetime.datetime.strptime(ts[:ts.index('.')],"%Y-%m-%dT%H:%M:%S")

      # check if we cross days
      if(ts_date.day != curr_day):
        chart.x_labels.append("%s/%s" % (ts_date.month, ts_date.day))
        curr_day = ts_date.day
      else:
        chart.x_labels.append("%s:%s:%s" % (ts_date.hour, ts_date.minute, ts_date.second))

    else:
      # appending placehoder
      chart.x_labels.append("")

  return chart

def getTestId():
  test_id = None
  evdata = getDBData('event')
  if not evdata:
    return

  evkeys = evdata.keys()
  if(len(evkeys) > 0):
    onephase = evdata[evkeys[0]].values()[0]
    if 'name' in onephase:
      test_id = str(onephase['name'])

  if test_id is None:
    raise Exception("testid missing from event-db")
  return test_id

def mkdir(path):
  if not os.path.exists(path):
      os.makedirs(path)
  else:
      shutil.rmtree(path)
      os.makedirs(path)

def prepareEnv(version, test_id, build = 'latest'):
  path = "system-test-results/%s/%s/%s" % (version, test_id, build)
  mkdir(path)
  return path


def parseArgs():
    """Parse CLI arguments"""
    usage = "usage: %prog bucket1,bucket2\n\n" + \
            "Example: python tools/plotter.py default,saslbucket <2.2.0> <build>"

    parser = OptionParser(usage)
    options, args = parser.parse_args()

    # at the least bucket is required
    if len(args) < 1 :
        parser.print_help()
        sys.exit()


    return options, args



class Build(object):

  def __init__(self, version, test, build):

    self.version = version
    self.test = test 
    self.build = build
    self.title = "%s, %s" % (version, build)
    self.path_full = "reports/system-test-results/%s/%s/%s" % (version,test,build) 
    self.info_path = "%s/_info.js" % (self.path_full) 
    self.spec = None
    self.buckets = None
    self.files = []
    self.unpackBuild()

  def unpackBuild(self):
    print "Unpack: "+self.path_full
    self.pullBuild()
    infoJS = self.getTestInfo()
    self.spec = str(infoJS['spec'])
    self.buckets = [str(bucket) for bucket in infoJS['buckets']]
    self.unzipFiles(infoJS['files'])

  def unzipFiles(self, files):
    for fileName in files:
      gzFile = str(fileName)
      csvFile = gzFile[:-3]
      gzPath = "reports/%s" % gzFile 
      csvPath  = "reports/%s" % csvFile 

      csv = open(csvPath, 'wb')
      gz = gzip.open(gzPath)
      for line in gz.readlines():
        csv.write(line)

      csv.close()
      gz.close()

      self.files.append(csvPath)
      

  def getTestInfo(self):
    f = open(self.info_path, 'rb')
    data = f.read()
    infoJS = json.loads(data)
    return infoJS

  def pullBuild(self):
    archive = 'reports/build.tar'
    f  = open(archive, 'wb')
    r=requests.get('%s/.cbfs/tar/system-test-results/%s/%s/%s' % (CBFS_HOST, self.version, self.test, self.build))
    f.write(r.content)
    f.close()
    t = tarfile.open(archive)
    t.extractall(path="reports")
    t.close()

  
def run(spec):


  baselineSpec = spec['baseline']
  comparisonSpecs  = spec['comparisions']

  baseline = Build(baselineSpec['version'],
                   baselineSpec['test'],
                   baselineSpec['build'])

  comparisons = []
  for comparison in comparisonSpecs:
    if((comparison['version'] != "Version") and
       (comparison['test'] != "Test") and
       (comparison['build'] != "Build")): 
      comparisons.append(Build(comparison['version'],
                                comparison['test'],
                                comparison['build']))
 
  report = generateGraphs(baseline, comparisons)
  report.pushReport()
  return report.url

if __name__ == "__main__":
  #TODO: run from cli!
  b = Build("2.2.0",
            "demo1",
            "780")

  c = [Build("2.2.0",
             "demo1",
             "781")]

  report = generateGraphs(b, c)
  report.pushReport()
  print report.local_path+'/'+report.name
