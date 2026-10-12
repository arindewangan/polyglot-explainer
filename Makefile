.PHONY: run

# Delegates to the track project root (track_2b/), in case `make run`
# is invoked from the repo root after the other track dirs are removed.
run:
	$(MAKE) -C track_2b run
