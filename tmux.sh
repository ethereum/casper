#!/bin/zsh

tmux start-server;

TMUX= tmux new-session -d -s simplecasper -n casper-daemons

tmux send-keys -t simplecasper:0.0 source\ \~/.zshrc C-m
tmux send-keys -t simplecasper:0.0 simplecasper\ -l\ casper:debug\ -d\ data0\ run\ 0\ --fake-account C-m

tmux splitw -t simplecasper:0
tmux select-layout -t simplecasper:0 tiled
tmux send-keys -t simplecasper:0.1 source\ \~/.zshrc C-m
tmux send-keys -t simplecasper:0.1 simplecasper\ -l\ casper:debug\ -d\ data1\ run\ 1\ --fake-account C-m

tmux splitw -t simplecasper:0
tmux select-layout -t simplecasper:0 tiled
tmux send-keys -t simplecasper:0.2 source\ \~/.zshrc C-m
tmux send-keys -t simplecasper:0.2 simplecasper\ -l\ casper:debug\ -d\ data2\ run\ 2\ --fake-account C-m

tmux splitw -t simplecasper:0
tmux select-layout -t simplecasper:0 tiled
tmux send-keys -t simplecasper:0.3 source\ \~/.zshrc C-m
tmux send-keys -t simplecasper:0.3 simplecasper\ -l\ casper:debug\ -d\ data3\ run\ 3\ --fake-account C-m

tmux select-layout -t simplecasper:0 tiled
tmux select-pane -t simplecasper:0.0
tmux select-window -t 0
tmux select-pane -t 0

if [ -z "$TMUX" ]; then
  tmux -u attach-session -t simplecasper
else
  tmux -u switch-client -t simplecasper
fi
