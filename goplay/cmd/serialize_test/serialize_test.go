/*

	Just testing serialization to see if it works.

*/

package main

import (
	"bytes"
	"encoding/gob"
	"fmt"
	"log"
)

type Foobar struct {
	Name string
	Data []byte
}

func main() {
	foobar := Foobar{
		Name: "foobar",
		Data: []byte{0, 1, 2, 3},
	}

	var buf bytes.Buffer

	encoder := gob.NewEncoder(&buf)
	if err := encoder.Encode(foobar); err != nil {
		log.Fatalf("Error encoding struct %s\n", err.Error())
	}

	var newFoobar Foobar

	decoder := gob.NewDecoder(&buf)

	if err := decoder.Decode(&newFoobar); err != nil {
		log.Fatalf("Error decoding struct: %s\n", err.Error())
	}

	fmt.Printf("Original binary: %s %d %d %d %d\n", foobar.Name, foobar.Data[0], foobar.Data[1], foobar.Data[2], foobar.Data[3])
	fmt.Printf("Decoded binary: %s %d %d %d %d\n", newFoobar.Name, newFoobar.Data[0], newFoobar.Data[1], newFoobar.Data[2], newFoobar.Data[3])
}
