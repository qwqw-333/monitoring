=> ERROR [4/4] RUN pip install --no-cache-dir -r requirements.txt                                                                                                                                                              1.8s
------
 > [4/4] RUN pip install --no-cache-dir -r requirements.txt:
1.642
1.642 [notice] A new release of pip is available: 25.0.1 -> 26.1.1
1.642 [notice] To update, run: pip install --upgrade pip
1.642 ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'
------
Dockerfile:7
--------------------
   5 |     COPY . .
   6 |
   7 | >>> RUN pip install --no-cache-dir -r requirements.txt
   8 |
   9 |     EXPOSE 9180
--------------------
ERROR: failed to build: failed to solve: process "/bin/sh -c pip install --no-cache-dir -r requirements.txt" did not complete successfully: exit code: 1


docker run --rm -it -v $(pwd)/exporter-fs/exporter:/app python3.12-slim ls -la /app
Unable to find image 'python3.12-slim:latest' locally
docker: Error response from daemon: pull access denied for python3.12-slim, repository does not exist or may require 'docker login': denied: requested access to the resource is denied

Run 'docker run --help' for more information
