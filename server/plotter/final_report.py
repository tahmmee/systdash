import pystache
import hashlib
import json
import os
import shutil
import requests

CBFS_HOST = 'http://cbfs.hq.couchbase.com:8484'

class PhaseReport(object):
  def __init__(self, name, phase_no, path, hideviations, bucket):
    self.name = name
    self.phase_no = phase_no
    self.path = path
    self.hideviations = hideviations
    self.bucket = bucket
    self.phase_href = "%s/system-test-results/%s" % (CBFS_HOST, path)

  def phase(self):
    view = []
    for stat_info in self.hideviations:
      stat , val = stat_info.iteritems().next()
      perc_change = val['diff']
      build = val['build']
      href = "/../../system-test-results/%s#%s" % (self.path,stat) # stat link
      template ={'stat' : stat,
                 'perc_change' : perc_change,
                 'build' : build,
                 'href' : href}

      if stat == 'phase_time':
        del template['href'] # no chart for phase_time

      view.append(template)


    return view

  def render(self):
    return pystache.render(self)

class FinalReport(object):
  def __init__(self, baseline, comparisions):
    self.name = "final_report.html"
    self.baseline = baseline
    self.comparisions = comparisions
    self.header = self.baseline.title
    self.desc = self.descFromSpec() 
    self.spec = baseline.spec 
    self.phases = {} 
    self.buckets = baseline.buckets
    self.local_path = self.genLocalPath()
    self.spec_path = "%s/%s/%s" % (CBFS_HOST, self.baseline.path_full[len('reports')+1:],  baseline.spec)
    self.url = "%s/system-test-results/%s/%s" % (CBFS_HOST, self.local_path, self.name)

  def genLocalPath(self):
    m = hashlib.md5()
    m.update(self.baseline.path_full)
    for cmpr in self.comparisions:
      m.update(cmpr.path_full)

    path_root = "reports/%s" % (m.hexdigest())
    for bucket in self.buckets:
      path = "%s/%s" % (path_root, bucket)
      mkdir(path)

    return path_root

  def compare(self):
    compare = ""
    for cmp in self.comparisions:
      compare = "%s %s" % (compare , cmp.title)
    return compare

  def descFromSpec(self):
    f=open(self.baseline.path_full+"/"+self.baseline.spec)
    js = json.loads(f.read())
    return js['desc']

  def render(self):
    header = pystache.render(self)
    phase_info = ""

    for phase_no in self.phases:

      phase_info = "%s <b>Phase: %s </b>" % (phase_info, phase_no)
      for phase_dict in self.phases[phase_no]:
        bucket, phase = phase_dict.iteritems().next()
        phase_info = "%s %s" % (phase_info, phase.render())
      phase_info = "%s</br>" % phase_info

    return header+phase_info

  def addPhase(self, name, phase_no, path, hideviations, bucket):
    newphase = PhaseReport(name,
                           phase_no,
                           path,
                           hideviations,
                           bucket)
    
    if not phase_no in self.phases:
      self.phases[phase_no] = [] 

    self.phases[phase_no].append({ bucket : newphase })

  def pushReport(self):
    # push phase charts
    for phase_no in self.phases:
      for phase_dict in self.phases[phase_no]:
        _, phase = phase_dict.iteritems().next()

        url = phase.phase_href
        print "Uploading: " + url
        headers = {'content-type': 'text/html'}
        data = open(phase.path,'rb')
        r = requests.put(url, data=data, headers=headers)

    # push final report html
    print "Uploading: " + self.url
    url = self.url
    headers = {'content-type': 'text/html'}
    data = open(self.local_path+'/'+self.name,'rb')
    r = requests.put(url, data=data, headers=headers)



def mkdir(path):
  if not os.path.exists(path):
      os.makedirs(path)
  else:
      shutil.rmtree(path)
      os.makedirs(path)
