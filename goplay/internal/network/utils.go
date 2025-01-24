package network

import (
	"bytes"
	"encoding/binary"
	"net"
)

func PollSize(c net.Conn) (uint32, error) {
	size := make([]byte, 4)

	if _, err := c.Read(size); err != nil {
		return 0, err
	}
	return binary.BigEndian.Uint32(size), nil
}

func PollType(c net.Conn) (PacketType, error) {
	packetType := make([]byte, 4)

	if _, err := c.Read(packetType); err != nil {
		return 0, err
	}
	return PacketType(binary.BigEndian.Uint32(packetType)), nil

}

func WrapWithSize(inBuf []byte) []byte {
	buffer := new(bytes.Buffer)

	// Write size
	binary.Write(buffer, binary.BigEndian, uint32(len(inBuf)))

	// Write data
	buffer.Write(inBuf)

	return buffer.Bytes()
}

func WrapWithType(inBuf []byte, packetType PacketType) []byte {
	buffer := new(bytes.Buffer)

	binary.Write(buffer, binary.BigEndian, uint32(packetType))
	buffer.Write(inBuf)

	return buffer.Bytes()
}
