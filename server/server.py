from flask import Response, Flask, jsonify, render_template, request, make_response, current_app
from datetime import timedelta
from functools import update_wrapper

from plotter import generate_report

app = Flask(__name__)

def crossdomain(origin=None, methods=None, headers=None,
    max_age=21600, attach_to_all=True,
    automatic_options=True):
  if methods is not None:
    methods = ', '.join(sorted(x.upper() for x in methods))
  if headers is not None and not isinstance(headers, basestring):
    headers = ', '.join(x.upper() for x in headers)
  if not isinstance(origin, basestring):
    origin = ', '.join(origin)
  if isinstance(max_age, timedelta):
    max_age = max_age.seconds

  def get_methods():
    if methods is not None:
      return methods

    options_resp = current_app.make_default_options_response()
    return options_resp.headers['allow']

  def decorator(f):
    def wrapped_function(*args, **kwargs):
      if automatic_options and request.method == 'OPTIONS':
        resp = current_app.make_default_options_response()
      else:
        resp = make_response(f(*args, **kwargs))
      if not attach_to_all and request.method != 'OPTIONS':
        return resp

      h = resp.headers

      h['Access-Control-Allow-Origin'] = origin
      h['Access-Control-Allow-Methods'] = get_methods()
      h['Access-Control-Max-Age'] = str(max_age)
      print headers
      if headers is not None:
        h['Access-Control-Allow-Headers'] = headers

      return resp

    f.provide_automatic_options = False
    f.required_methods = ['OPTIONS']
    return update_wrapper(wrapped_function, f)
  return decorator

@app.route("/report",  methods=['POST', 'OPTIONS'])
@crossdomain(origin='http://cbfs.hq.couchbase.com:8484', headers='Content-Type')
def generateReport():
  spec = request.json
  try:
    url = generate_report.run(spec)
    response = make_response(url)
    response.headers['Access-Control-Allow-Origin'] = "http://cbfs.hq.couchbase.com:8484"
    return response 
  except Exception as ex:
    emsg = "error rendering report: "+str(ex)
    print emsg
    return emsg, 200

app.run(host='plum-003.hq.couchbase.com', port=80)



