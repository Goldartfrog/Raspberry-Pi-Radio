package main

import (
	"player/internal/network"
)

func main() {
	network.RunServer(13337)
	select {}
}
