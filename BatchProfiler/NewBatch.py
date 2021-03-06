#!/usr/bin/env ./python-2.6.sh
#
# Start a batch operation from a web page
#
# CellProfiler is distributed under the GNU General Public License.
# See the accompanying file LICENSE for details.
#
# Copyright (c) 2003-2009 Massachusetts Institute of Technology
# Copyright (c) 2009-2014 Broad Institute
# All rights reserved.
#
# Please see the AUTHORS file for credits.
#
# Website: http://www.cellprofiler.org

import cgitb
cgitb.enable()
print "Content-Type: text/html\r"
print "\r"
import sys
import cgi
import os
import numpy as np
import traceback
import urllib
import cellprofiler.preferences
cellprofiler.preferences.set_headless()
import cellprofiler.measurements as cpmeas
from cellprofiler.modules.createbatchfiles import F_BATCH_DATA_H5
import RunBatch
import email.message
import email.mime.text
import socket
from cStringIO import StringIO

SENDMAIL="/usr/sbin/sendmail"
batch_url = "http://%s/batchprofiler/cgi-bin/FileUI/CellProfiler/BatchProfiler/ViewBatch.py"%(socket.gethostname())

form_data = cgi.FieldStorage()
myself = os.path.split(__file__)[1]
if len(myself) == 0:
    myself = __file__
    
def show_directory(key, title, default, hidden_vars):
    '''Show the directory structure for the variable given by the key
    
    key - key into form_data
    title - the user-visible title of the field
    default - default value for the field
    
    returns the current value of the key
    '''
    if form_data.has_key(key):
        value = form_data[key].value
    else:
        value = default
    
    paths = []
    path = value
    hvs = hidden_vars_inputs(hidden_vars)
    while True:
        head,tail = os.path.split(path)
        if len(tail) == 0:
            paths.insert(0,(head, path))
            break
        paths.insert(0,(tail, path))
        path = head

    print '''<div id="%(key)s_div">
    <div>
        <label for='input_%(key)s'>%(title)s:&nbsp;</label><input type='text' 
                          size='40'
                          id='input_%(key)s'
                          name='%(key)s' 
                          value='%(value)s'/>
        <input type='button' value='Browse...' 
            onclick="javascript:go_to_key('%(key)s')"/>
    </div>
    '''%(locals())
    for dirname, dirpath in paths:
        all_keys = dict(hidden_vars)
        all_keys[key] = dirpath
        url = "%s?%s"%(myself, urllib.urlencode(all_keys))
        print '''<ul><li><a href='%(url)s'>%(dirname)s</a></li>'''%(locals())
    filenames = [(filename, os.path.join(value, filename))
                 for filename in os.listdir(value)
                 if os.path.isdir(os.path.join(value, filename))]
    filenames.sort()
    if len(filenames):
        print '''<ul>'''
        for dirname, dirpath in filenames:
            all_keys = dict(hidden_vars)
            all_keys[key] = dirpath
            url = "%s?%s"%(myself, urllib.urlencode(all_keys))
            print '''<li><a href='%(url)s'>%(dirname)s</a></li>'''%(locals())
        print '''</ul>'''
    print ''.join(['</ul>']*len(paths))
    print '''</div>
'''
    return value

def hidden_vars_inputs(hidden_vars):
    '''Create hidden input elements for each key in hidden_vars'''
    s = ''
    for key in hidden_vars.keys():
        s+= '''<input type='hidden' name='%s' value='%s'/>'''%(key,hidden_vars[key])
    return s

def lookup(key, default):
    if form_data.has_key(key):
        return form_data[key].value
    else:
        return default

def minus_key(d, key):
    d = dict(d)
    del d[key]
    return d
def SendMail(recipient,body):
    if os.name != 'nt':
        pipe=os.popen("%s -t"%(SENDMAIL),"w")
        pipe.write("To: %s\n"%(recipient))
        pipe.write("Subject: Batch %d submitted\n"%(batch_id))
        pipe.write("Content-Type: text/html\n")
        pipe.write("\n")
        pipe.write(body)
        pipe.write("\n")
        pipe.close()
    return

keys = { 'data_dir':lookup('data_dir', '/imaging/analysis'),
         'email':lookup('email', 'user@broadinstitute.org'),
         'queue':lookup('queue', 'hour'),
         'project':lookup('project','imaging'),
         'priority':lookup('priority','50'),
         'write_data':lookup('write_data','no'),
         'batch_size':lookup('batch_size','10'),
         'memory_limit':lookup('memory_limit','2000'),
         'timeout':lookup('timeout','30'),
         'revision':lookup('revision','10997'),
         'url':myself
         }

batch_file = os.path.join(keys['data_dir'], F_BATCH_DATA_H5)
has_image_sets = False
error_message = None
if os.path.exists(batch_file):
    print "<div>Found %s</div>" % batch_file
    print "<span style='visibility:hidden'>"
    try:
        measurements = cpmeas.Measurements(filename=batch_file, mode="r")
        image_numbers = measurements.get_image_numbers()
        if measurements.has_feature(cpmeas.IMAGE, cpmeas.GROUP_NUMBER):
            group_numbers = measurements[cpmeas.IMAGE, cpmeas.GROUP_NUMBER, image_numbers]
            group_indexes = measurements[cpmeas.IMAGE, cpmeas.GROUP_INDEX, image_numbers]
            has_groups = len(np.unique(group_numbers)) > 1
        else:
            has_groups = False
        has_image_sets = True
    except:
        error_message = "Failed to open %s\n%s" % (batch_file, traceback.format_exc())
        error_message = error_message.replace("\n","<br/>")
    print "</span>"
    
if (form_data.has_key('submit_batch') and 
    form_data['submit_batch'].value == 'yes' and
    has_image_sets):
    #
    # Submit the batch according to the directions
    #
    batch = {
        "email":         form_data["email"].value,
        "queue":         form_data["queue"].value,
        "priority":      int(form_data["priority"].value) if form_data.has_key("priority") else 50,
        "project":       form_data["project"].value if form_data.has_key("project") else 'imaging',
        "data_dir":      form_data["data_dir"].value,
        "write_data":    (form_data.has_key("write_data") and 1) or 0,
        "batch_size":    int(form_data["batch_size"].value),
        "memory_limit":  float(form_data["memory_limit"].value) if form_data.has_key("memory_limit") else 2000,
        "timeout":       float(form_data["timeout"].value),
        "cpcluster":     "CellProfiler_2_0:/imaging/analysis/CPCluster/CellProfiler-2.0/%s"%form_data["revision"].value,
        "batch_file":    batch_file,
        "runs":          []
    }
    if has_groups:
        # Has grouping
        first_last = np.hstack([[True], group_numbers[1:] != group_numbers[:-1], [True]])
        gn = group_numbers[first_last[:-1]]
        first = image_numbers[first_last[:-1]]
        last = image_numbers[first_last[1:]]
        for g, start, end in zip(gn, first, last):
            status_file_name = ("%s/status/Batch_%d_to_%d_DONE.mat"%
                                (batch["data_dir"], start, end))
            run = { "start": start,
                    "end": end,
                    "group": None,
                    "status_file_name":status_file_name}
            batch["runs"].append(run)
    else:
        batch_size = 10
        if form_data.has_key("batch_size"):
            batch_size = int(form_data["batch_size"].value)
        for i in image_numbers[::batch_size]:
            start = i
            end = min(start + batch_size -1, max(image_numbers))
            status_file_name = ("%s/status/Batch_%d_to_%d_DONE.mat"%
                                (batch["data_dir"], start, end))
            run = { "start": start,
                    "end": end,
                    "group": None,
                    "status_file_name":status_file_name}
            batch["runs"].append(run)


    batch_id = RunBatch.CreateBatchRun(batch)

    email_text=[]
    email_text.append("<html>")
    email_text.append("<head><title>Batch # %d</title>"%(batch_id))
    email_text.append("<style type='text/css'>")
    email_text.append("""
table {
    border-spacing: 0px;
    border-collapse: collapse;
}
td {
    text-align: left;
    vertical-align: baseline;
    padding: 0.1em 0.5em;
    border: 1px solid #666666;
}
""")
    email_text.append("</style></head>")
    email_text.append("</head>")
    email_text.append("<body>")
    email_text.append("<h1>Results for batch # <a href='%s?batch_id=%d'>%d</a></h1>"%(batch_url,batch_id,batch_id))
    ##email_text.append("<table>")
    ##email_text.append("<th><tr><td>First image set</td><td>Last image set</td><td>job #</td></tr></th>")
    ##for result in results:
        ##email_text.append("<tr><td>%(start)d</td><td>%(end)d</td><td>%(job)d</td></tr>"%(result))
        ##email_text.append("<tr><td>%(start)d</td><td>%(end)d</td></tr>"%(result))
    ##print "result=%s"%(result[job])
    ##email_text.append("</table>")
    email_text.append("Data Directory: %s"%(keys["data_dir"]))
    email_text.append("</body>")
    email_text.append("</html>")
    email_text= '\n'.join(email_text)

    SendMail(keys["email"],email_text)

    results = RunBatch.RunAll(batch_id)


    print '''<html>
    <head><title>Batch #%(batch_id)d</title>
    <style type='text/css'>
table {
    border-spacing: 0px;
    border-collapse: collapse;
}
td {
    text-align: left;
    vertical-align: baseline;
    padding: 0.1em 0.5em;
    border: 1px solid #666666;
}
</style></head>
</head>
<body>'''%(locals())

    print '''
<h1>Results for batch # <a href='ViewBatch.py?batch_id=%(batch_id)d'>%(batch_id)d</a></h1>
<table>
<thead><tr><th>First image set</th><th>Last image set</th>'''%(locals())
    print '<th>job #</th></tr></thead>'
    
    for i,result in enumerate(results):
        print "<tr><td>%(start)d</td><td>%(end)d</td>"%(result)
        print "<td>%(job)d</td></tr>"%(result)
    print "</table></body></html>"
    sys.exit()
    
print '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html lang="en-US" xml:lang="en-US" xmlns="http://www.w3.org/1999/xhtml">
    <head>
         <title>CellProfiler 2.0 Batch submission</title>
         <script language='JavaScript'>
function go_to_key(key) {
    url='%(myself)s'
    add_char = "?"
    all_k = new Array("data_dir","email","queue","priority",
                        "project","batch_size","memory_limit",
                        "timeout","revision")
    for (k in all_k) {
        v = document.getElementById('input_'+all_k[k])
        url = url+add_char+all_k[k]+'='+escape(v.value)
        add_char = "&"
    }
    v = document.getElementById('input_write_data')
    if (v.checked)
    {
        url = url + add_char + "write_data=yes"
    } else {
        url = url + add_char + "write_data=no"
    }
parent.location = url+"#input_"+key
}
         </script>
    </head>
    <body>
    <H1>CellProfiler 2.0 Batch submission</H1>
    <div>
    <p>There are several different types of batch files that CellProfiler can 
    generate, depending on the version of CellProfiler used: 
    <ul>
    <li>MAT file produced by CellProfiler svn revision 11310 or lower <b>OR</b> release 11710 and earlier: Use the 
    website, <a href="http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/development/CellProfiler_2.0/NewBatch.py">
    http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/development/CellProfiler_2.0/NewBatch.py</a>.</li>
    <li>HDF5 file produced CellProfiler svn revision 11311 or above (e.g., trunk builds): Use the 
    website, <a href="http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/CellProfiler2.0/CellProfiler/BatchProfiler/NewBatch.py">
    http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/CellProfiler2.0/CellProfiler/BatchProfiler/NewBatch.py</a>.</li>
    <li>HDF5 file produced by the CellProfiler FileUI branch: Use the
    website, <a href="http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/FileUI/CellProfiler/BatchProfiler/NewBatch.py">
    http://imagingweb.broadinstitute.org/batchprofiler/cgi-bin/FileUI/CellProfiler/BatchProfiler/NewBatch.py</a></li>
    </ul></p>
    <p>For details on the settings below and for general help on submitting a CellProfiler job to the LSF, please see this
    <a href="http://dev.broadinstitute.org/imaging/privatewiki/index.php/How_To_Use_BatchProfiler">page</a>.</p>
    Submit a %(F_BATCH_DATA_H5)s file created by CellProfiler 2.0. You need to
    specify the default output folder, which should contain your
    Batch_data file for the pipeline. In
    addition, there are some parameters that tailor how the batch is run.
    </div>
    '''%(globals())

print '''<form action='%(url)s' method='POST'>
<input type='hidden' name='submit_batch' value='yes'/>
<table style='white-space=nowrap'>
<tr><th>E-mail:</th>
<td><input type='text' size="40" id='input_email' name='email' value='%(email)s'/></td></tr>
<tr><th>Queue:</th>
<td><select id='input_queue' name='queue'>
'''%(keys)
for queue in ('hour', 'week', 'priority'):
    selected = 'selected="selected"' if queue == keys['queue'] else ''
    print '''<option value='%(queue)s' %(selected)s>%(queue)s</option>'''%(locals())

print '''</select></td></tr>'''
keys_plus = keys.copy()
keys_plus["write_data_checked"] = "" if keys["write_data"] == "no" else 'checked="yes"'
print '''
<tr><th>Priority:</th>
<td><input type='text' id='input_priority' name='priority' value='%(priority)s'/></td></tr>
<tr><th>Project:</th>
<td><input type='text' id='input_project' name='project' value='%(project)s'/></td></tr>
<tr><th>Batch size:</th>
<td><input type='text' id='input_batch_size' name='batch_size' value='%(batch_size)s'/></td></tr>
<tr><th>Memory limit:</th>
<td><input type='text' id='input_memory_limit' name='memory_limit' value='%(memory_limit)s'/></td></tr>
<tr><th>Write data:</th>
<td><input type='checkbox' id='input_write_data' name='write_data' value='yes' %(write_data_checked)s/></td></tr>
<tr><th>Timeout:&nbsp;</th>
<td><input type='text' id='input_timeout' name='timeout' value='%(timeout)s'/></td></tr>
'''%(keys_plus)
print '''<tr><th>SVN revision:</th><td><select name='revision' id='input_revision'>'''
vroot = '/imaging/analysis/CPCluster/CellProfiler-2.0'
vdirs = list(os.listdir(vroot))
vdirs.sort()
for filename in vdirs:
    vpath = os.path.join(vroot, filename)
    if not os.path.isdir(vpath):
        continue
    print '''<option %s>%s</option>'''%('selected="selected"' if filename == keys['revision'] else '',filename)
print '''</select> (at /imaging/analysis/CPCluster/CellProfiler-2.0/)</td></tr></table>'''
show_directory('data_dir','Data output directory',keys['data_dir'], 
               minus_key(keys,'data_dir'))
if has_image_sets:
    print '''<div><input type='submit' value='Submit batch'/></div>'''
    if has_groups:
        group_counts = np.bincount(group_numbers)
        print '<h2>Groups</h2>'
        print '<table><tr>'
        print '<th>Group #</th>'
        print '<th># of image sets</th></tr>'
        for group_number in sorted(np.unique(group_numbers)):
            print '<tr>'
            print '<td>%d</td><td>%d</td></tr>'%(group_number, group_counts[group_number])
        print '</table>'
    else:    
        print '<div>%s has %d image sets</div>'%(F_BATCH_DATA_H5, len(image_numbers))
elif error_message is not None:
    print error_message
else:
    print 'Directory does not contain a %s file' % F_BATCH_DATA_H5
print '</form>'
print '</body></html>'

