=> ERROR [freeswitch-exporter 4/4] RUN pip install -r requirements.txt                                                                                                                                                         1.9s
 => [umz-event-detector] resolving provenance for metadata file                                                                                                                                                                 0.0s
------
 > [freeswitch-exporter 4/4] RUN pip install -r requirements.txt:
1.535 ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'
1.740
1.740 [notice] A new release of pip is available: 24.0 -> 26.1.1
1.740 [notice] To update, run: pip install --upgrade pip
------
[+] build 0/2
 ⠙ Image monitoring-umz-event-detector  Building                                                                                                                                                                                44.8s
 ⠙ Image monitoring-freeswitch-exporter Building                                                                                                                                                                                44.8s
Dockerfile:7

--------------------

   5 |     COPY . .

   6 |

   7 | >>> RUN pip install -r requirements.txt

   8 |

   9 |     EXPOSE 9180

--------------------

target freeswitch-exporter: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully: exit code: 1

➜  monitoring git:(feat/fs-monitoring)
