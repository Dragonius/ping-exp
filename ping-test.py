#!/usr/bin/env python
from subprocess import Popen, PIPE
import re
from multiprocessing import Process, Queue
import matplotlib.pyplot as plt

COLORS=['#3194e0', '#49db50', '#e03131']
TITLE_FONT = {'family': 'sans-serif', 'weight': 'bold', 'size': 14}
COUNT=28800
COUNT=500
INTERVAL=.2
HOST='69.41.192.2'

# Specific to ping on Linux?
def ping(host, qos=0, interval=1, count=5, flood=False, debug_prefix=''):
	"""Method to obtain some basic information about the capture file using the capinfos command."""
	result = {}
	result['responses'] = []

	# Construct the arguments to Popen.
	args = ['ping'] # The binary to execute.
	args.append('-i %.3f'%(interval))
	args.append('-Q %i'%(int(qos)))
	args.append('-c %i'%(count))
	if flood:
		args.append('-f')
	args.append(host)

	# Run the ping command.
	try:
		p = Popen(args, shell=False, stdout=PIPE, stderr=PIPE)
	except OSError:
		# Could not execute
		return None

	# Wait for it to complete.
	ret = p.wait()
	if ret != 0:
		# Failed to execute ping.
		for line in p.stderr.readlines():
			print line
		return None

	# Regular expressions to obtain the information.
	response_re = re.compile('icmp_seq=(?P<icmp_seq>\d+) ttl=(?P<ttl>\d+) time=(?P<time>\d+(\.\d+|)) ms')
	summary_re = re.compile('(?P<transmitted>\d+) packets transmitted, (?P<received>\d+) received, (\+(?P<errors>\d+) errors, |)(?P<packet_loss>\d+)% packet loss, time (?P<time>\d+(\.\d+|))ms')
	rtt_summary_re = re.compile('rtt min/avg/max/mdev = (?P<min>\d+(\.\d+|))/(?P<avg>\d+(\.\d+|))/(?P<max>\d+(\.\d+|))/(?P<mdev>\d+(\.\d+|)) ms')

	# Extract the few required fields.
	for line in p.stdout.readlines():
		line = line.rstrip()
		print debug_prefix, line

		# Match the response lines.
		m = response_re.search(line)
		if m != None:
			result['responses'].append((int(m.group('icmp_seq')), int(m.group('ttl')), float(m.group('time'))))

		# Match the packet summary line.
		m = summary_re.search(line)
		if m != None:
			result['summary'] = {'transmitted': int(m.group('transmitted')),
						'received': int(m.group('received')),
						'packet_loss': int(m.group('packet_loss')),
						'time': float(m.group('time'))}

		# Match the RTT summary line.
		m = rtt_summary_re.search(line)
		if m != None:
			result['rtt_summary'] = {'min': float(m.group('min')),
						'avg': float(m.group('avg')),
						'max': float(m.group('max')),
						'mdev': float(m.group('mdev'))}

	return result

def do_ping(results_q, experiment_id, host, qos=0, interval=1, count=5, flood=False):
	results = ping(host, qos=qos, interval=interval, count=count, flood=flood, debug_prefix=experiment_id)

	results_q.put((experiment_id, results))

if __name__ == '__main__':
	# Create a queue for receiving the results.
	results_q = Queue()

	# Setup the experiments.
	experiments = []
	experiments.append({'args': (results_q, 'Default', '%s'%(HOST)), 'kwargs': {'qos': 0, 'interval': INTERVAL, 'count': COUNT}})
	experiments.append({'args': (results_q, 'High priority', '%s'%(HOST)), 'kwargs': {'qos': 16, 'interval': INTERVAL, 'count': COUNT}})
	experiments.append({'args': (results_q, 'Low priority', '%s'%(HOST)), 'kwargs': {'qos': 8, 'interval': INTERVAL, 'count': COUNT}})

	# Start each experiment.
	for num,experiment in enumerate(experiments):
		w = Process(target=do_ping, args=experiment['args'], kwargs=experiment['kwargs'])
		w.start()

	# Create the figure.
	fig = plt.figure(figsize=(10,6), facecolor='w')
	fig.subplots_adjust(left=0.09, right=0.96, top=0.92, bottom=0.07, wspace=.4, hspace=.4)

	# Create the response time graph.
	ax = fig.add_subplot(2,1,1)
	ax.set_title('Latency vs time', TITLE_FONT)
	ax.set_xlabel('Time (s)')
	ax.set_ylabel('Latency (ms)')

	# Create the packet loss bar graph.
	loss_graph = fig.add_subplot(2,4,5)
	loss_graph.set_title('Packet loss', TITLE_FONT)
	loss_graph.set_xlabel('Traffic class')
	loss_graph.set_ylabel('Packet loss (%)')
	loss_graph.set_xticks([])

	# Create the average latency graph.
	latency_graph = fig.add_subplot(2,4,6)
	latency_graph.set_title('Latency', TITLE_FONT)
	latency_graph.set_xlabel('Traffic class')
	latency_graph.set_ylabel('Average (ms)')
	latency_graph.set_xticks([])

	# Create the mean deviation bar graph.
	mdev_graph = fig.add_subplot(2,4,7)
	mdev_graph.set_title('Latency', TITLE_FONT)
	mdev_graph.set_xlabel('Traffic class')
	mdev_graph.set_ylabel('Mean deviation')
	mdev_graph.set_xticks([])

	# Wait for a result from each experiment and store them.
	results = {}
	for num in range(len(experiments)):
		tmp = results_q.get()
		print "Got results for %(name)s" %{'name': tmp[0]}

		# Store all of the results.
		results[tmp[0]] = tmp[1]

	# Plot the response time data.
	for num,result in enumerate(results):
		print "DD:", result
		points = [(icmp_seq / (1 / INTERVAL), time) for (icmp_seq, ttl, time) in results[result]['responses']]
		print "LEN:", len(points)
		points = zip(*points)
		ret = ax.plot(points[0], points[1], c=COLORS[num])

	# Plot the packet loss graph.
	loss = [results[key]['summary']['packet_loss'] for key in results.keys()]
	print "LOSS keys:", results.keys()
	print "LOSS:", loss
	ret = loss_graph.bar([x for x in range(len(loss))], loss, width=1, color=COLORS)

	# Plot the average latency graph.
	latency = [results[key]['rtt_summary']['avg'] for key in results.keys()]
	print "LATENCY keys:", results.keys()
	print "LATENCY:", latency
	ret = latency_graph.bar([x for x in range(len(latency))], latency, width=1, color=COLORS)

	# Plot the mean deviation graph.
	mdev = [results[key]['rtt_summary']['mdev'] for key in results.keys()]
	print "MDEV keys:", results.keys()
	print "MDEV:", mdev
	ret = mdev_graph.bar([x for x in range(len(mdev))], mdev, width=1, color=COLORS)

	# Add the legend.
	plt.legend(ret, [key for key in results.keys()], loc=(1.1,.2))

	#print results

	#f = open('output.png', 'w')
	#cjplt.savefig(f)
	#f.close()

	plt.show()