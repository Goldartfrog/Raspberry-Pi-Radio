package download

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
)

func Download(link string, as string) {
	os.Executable()

	// yt-dlp -f "worstvideo*+worstaudio/worst"
	cmd := exec.Command("yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", as, "-x", link)
	var stdout, stderr bytes.Buffer

	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	if err != nil {
		fmt.Println(stderr.String())
	} else {
		fmt.Println(stdout.String())
	}

}

/*
TODO:
Async download that passes to given channel that the download is finished
*/
func GoDownload() {}
