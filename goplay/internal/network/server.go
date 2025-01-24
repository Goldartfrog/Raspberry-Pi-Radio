package network

import (
	"fmt"
	"log"
	"net"
)

func RunServer(port int) {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		log.Fatalf("RunServer()=:: Error with listening: %s\n", err.Error())
	}
	defer l.Close()

	log.Printf("Listening on port %d\n", port)

	for {
		c, err := l.Accept()
		if err != nil {
			log.Printf("RunServer()=:: Error with incoming connection: %s\n", err.Error())
			continue
		}

		// TEMP: Send an example youtube packet to the connection
		// TEMP SECTION START
		ys := YoutubeSend{Link: "https://www.youtube.com/watch?v=-wwZZLys0DE"}

		buf := EncodePacket(PacketYoutubeSend, ys)
		c.Write(buf)

		// TEMP SECTION END

		go handleConnection(c)
	}
}

func handleConnection(conn net.Conn) {
	for {
		// Get Size
		size, err := PollSize(conn)
		if err != nil {
			log.Printf("handleConnection()=:: Error with reading size: %s from ip %s\n", err.Error(), conn.RemoteAddr())
			return
		}
		// Get Buffer
		readBytes := uint32(0)
		buf := make([]byte, size)

		for readBytes < size {
			n, err := conn.Read(buf[readBytes:])
			if err != nil {
				log.Printf("handleConnection()=:: Error with reading packet: %s from ip %s\n", err.Error(), conn.RemoteAddr())
				return
			}
			readBytes += uint32(n)
		}
		// Unwrap Packet

		//packetType, s, err := DecodePacket(buf)
		//if err != nil {
		//	log.Printf("handleConnection()=:: Error reading packet: %s from ip %s\n", err.Error(), conn.RemoteAddr())
		//	return
		//}

		//_ = packetType
		//_ = s
	}
}
