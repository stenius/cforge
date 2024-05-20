package main

import (
	"archive/tar"
	"compress/gzip"
	"fmt"
	"io"
	"log"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"gopkg.in/src-d/go-git.v4"
)

func cloneRepo(repoURL, dir string) (*git.Repository, error) {
	repo, err := git.PlainClone(dir, false, &git.CloneOptions{
		URL:      repoURL,
		Progress: os.Stdout,
	})
	if err != nil {
		return nil, err
	}
	return repo, nil
}

func getCommitSHA(repo *git.Repository) (string, error) {
	head, err := repo.Head()
	if err != nil {
		return "", err
	}
	return head.Hash().String(), nil
}

func runMake(dir string, logFile *os.File) error {
	cmd := exec.Command("make", "-C", dir)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	return cmd.Run()
}

func listFiles(dir string) (map[string]bool, error) {
	files := make(map[string]bool)
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		relativePath := strings.TrimPrefix(path, dir+string(filepath.Separator))
		files[relativePath] = true
		return nil
	})
	return files, err
}

func createTarball(newFiles map[string]bool, dir, tarballPath string) error {
	tarball, err := os.Create(tarballPath)
	if err != nil {
		return err
	}
	defer tarball.Close()

	gw := gzip.NewWriter(tarball)
	defer gw.Close()

	tw := tar.NewWriter(gw)
	defer tw.Close()

	for file := range newFiles {
		filePath := filepath.Join(dir, file)
		info, err := os.Stat(filePath)
		if err != nil {
			return err
		}

		header, err := tar.FileInfoHeader(info, file)
		if err != nil {
			return err
		}
		header.Name = file

		if err := tw.WriteHeader(header); err != nil {
			return err
		}

		if !info.IsDir() {
			f, err := os.Open(filePath)
			if err != nil {
				return err
			}
			defer f.Close()

			if _, err := io.Copy(tw, f); err != nil {
				return err
			}
		}
	}

	return nil
}

func parseRepoURL(repoURL string) (string, string, error) {
	u, err := url.Parse(repoURL)
	if err != nil {
		return "", "", err
	}

	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) < 2 {
		return "", "", fmt.Errorf("invalid repository URL: %s", repoURL)
	}

	return parts[0], strings.TrimSuffix(parts[1], ".git"), nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatalf("Usage: %s <repo-url>", os.Args[0])
	}

	// clone the repo provided in the arugments to /tmp/cloned-repo and grab the SHA of the latest commit
	repoURL := os.Args[1]
	dir := filepath.Join(os.TempDir(), "cloned-repo")
	artifactDir := os.Getenv("ARTIFACT_DIR")
	if artifactDir == "" {
		artifactDir = "."
	}

	gitUser, gitRepo, err := parseRepoURL(repoURL)
	if err != nil {
		log.Fatalf("Failed to parse repository URL: %v", err)
	}

	outputDir := filepath.Join(artifactDir, gitUser, gitRepo)
	if err := os.MkdirAll(outputDir, os.ModePerm); err != nil {
		log.Fatalf("Failed to create output directory: %v", err)
	}

	fmt.Println("Cloning repository...")
	repo, err := cloneRepo(repoURL, dir)
	if err != nil {
		log.Fatalf("Failed to clone repository: %v", err)
	}

	sha, err := getCommitSHA(repo)
	if err != nil {
		log.Fatalf("Failed to get commit SHA: %v", err)
	}



	logFile, err := os.Create(filepath.Join(outputDir, fmt.Sprintf("%s.log", sha)))
	if err != nil {
		log.Fatalf("Failed to create log file: %v", err)
	}
	defer logFile.Close()

	// get a list of files so we know what files are new that need to get added to the artifact
	initialFiles, err := listFiles(dir)
	if err != nil {
		log.Fatalf("Failed to list initial files: %v", err)
	}

	fmt.Println("Running make...")
	if err := runMake(dir, logFile); err != nil {
		log.Fatalf("Build failed: %v", err)
	}

	newFiles, err := listFiles(dir)
	if err != nil {
		log.Fatalf("Failed to list new files: %v", err)
	}

	// keep track of all new files and add them to a artifact tarball
	createdFiles := make(map[string]bool)
	for file := range newFiles {
		if !initialFiles[file] {
			createdFiles[file] = true
		}
	}

	if len(createdFiles) > 0 {
	  tarballPath := filepath.Join(outputDir, fmt.Sprintf("%s.tar.gz", sha))
		if err := createTarball(createdFiles, dir, tarballPath); err != nil {
			log.Fatalf("Failed to create tarball: %v", err)
		}
		fmt.Printf("Tarball created: %s\n", tarballPath, sha)
	} else {
		fmt.Println("No new files created.")
	}
}
