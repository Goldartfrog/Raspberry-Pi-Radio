package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"player/internal/audio"
	"player/internal/download"
	"player/internal/network"
)

func main() {
	// Find via. ifconfig | grep netmask
	serverPtr := flag.String("ip", "192.168.86.140", "Local ip address (not global)")

	flag.Parse()

	conn, err := net.Dial("tcp", fmt.Sprintf("%s:13337", *serverPtr))
	if err != nil {
		log.Fatalf("Error connecting: %s\n", err.Error())
	}

	fmt.Printf("Success connecting to server on port %d\n", 13337)

	// For now just poll for an arbitrary YoutubeRequest packet

	for {
		t, err := network.PollType(conn)
		if err != nil {
			log.Fatalf("Error getting size: %s\n", err.Error())
		}
		fmt.Printf("Type: %d\n", t)
		n, err := network.PollSize(conn)
		fmt.Printf("Size: %d\n", n)
		if err != nil {
			log.Fatalf("Error getting size: %s\n", err.Error())
		}

		buf := make([]byte, n)
		_, _ = conn.Read(buf)
		rawPacket, err := network.DecodePacket(t, buf)
		if err != nil {
			log.Fatalf("Error getting packet: %s\n", err.Error())
		}

		ys := rawPacket.(network.YoutubeSend)
		_ = ys
		fmt.Printf("Link: %s\n", ys.Link)

		download.Download(ys.Link, "output.wav")
		audio.PlayFile("output.wav")
	}
}
