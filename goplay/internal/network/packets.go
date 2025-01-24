package network

import (
	"bytes"
	"encoding/gob"
	"log"
)

type PacketType uint32

const (
	PacketHeartbeat PacketType = iota
	PacketYoutubeRequest
	PacketYoutubeSend
)

type YoutubeRequest struct {
	Link string
}

type YoutubeSend struct {
	Link string
}

/*
Takes packet type and packet and returns Packet to send
*/
func EncodePacket(packetType PacketType, packet interface{}) []byte {

	var buffer bytes.Buffer
	encoder := gob.NewEncoder(&buffer)
	if err := encoder.Encode(packet); err != nil {
		log.Fatalf("EncodePacket()=:: Error encoding: %s\n", err.Error())
	}

	return WrapWithType(WrapWithSize(buffer.Bytes()), packetType)
}

/*
Takes buffer sent by tcp and returns arbitrary
*/
func DecodePacket(packetType PacketType, buf []byte) (interface{}, error) {
	buffer := bytes.NewBuffer(buf)
	decoder := gob.NewDecoder(buffer)

	var err error

	switch packetType {
	case PacketYoutubeSend:
		var ys YoutubeSend
		if err = decoder.Decode(&ys); err != nil {
			break
		}

		return ys, nil
	}

	return 0, err
}
