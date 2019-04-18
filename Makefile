IMAGE="metal3-io/ironic"
LISTEN_IP="127.0.0.1"

.PHONY: help
help:
	@echo "Targets:"
	@echo "  docker -- build the docker image"
	@echo "  docker-run -- run the docker containers"
	@echo "  docker-test -- run tests against the containers"
	@echo "  docker-clean -- stop and remove containers"

.PHONY: docker
docker:
	docker build -t $(IMAGE) . -f Dockerfile

.PHONY: docker-run
docker-run:
	docker run -d --net host --privileged --name mariadb --entrypoint /bin/runmariadb $(IMAGE)
	docker run -d --net host --privileged --name dnsmasq -e "IP=$(LISTEN_IP)" --entrypoint /bin/rundnsmasq $(IMAGE)
	docker run -d --net host --privileged --name httpd -e "IP=$(LISTEN_IP)" --entrypoint /bin/runhttpd $(IMAGE)
	docker run -d --net host --privileged --name ironic -e "IP=$(LISTEN_IP)" $(IMAGE)

.PHONY: docker-test
docker-test:
	./test/smoke-test.sh

.PHONY: docker-clean
docker-clean:
	docker stop mariadb dnsmasq httpd ironic || true
	docker rm mariadb dnsmasq httpd ironic || true
