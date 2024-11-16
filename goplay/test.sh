#!/bin/bash
#GOBIN=/home/goldartfrog/dev/goplay/bin go install cmd/player/player.go
#GOBIN=/home/goldartfrog/dev/goplay/bin go install cmd/record/recorder.go
#GOBIN=${PWD}/bin go install cmd/serialize_test/serializer.go
GOBIN=$PWD/bin go install ./...