### Обновление

```
# sudo apt update
# sudo apt upgrade
```

### Установка python 3.7

```
# sudo apt install software-properties-common
# sudo add-apt-repository ppa:deadsnakes/ppa
# sudo apt install python3.7
# sudo apt install python3-pip
# python3.7 -m pip install pip
```

### Опциональные алиасы для python 3.7

```
# sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1
# sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 2
```

### Полезности

```
# sudo apt install tmux htop nginx supervisor git zsh tree
```

### Установка пароля

```
# sudo passwd $(whoami)
```

### Настройка zsh

```
# sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

Тема оформления - **ZSH_THEME="gianu"**

### Установка docker

Из инструкции [digitalocean](https://www.digitalocean.com/community/tutorials/docker-ubuntu-18-04-1-ru)

```
# sudo apt update
# sudo apt install apt-transport-https ca-certificates curl software-properties-common
# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
# sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable"
# sudo apt update
# sudo apt install docker-ce
# sudo systemctl status docker
# sudo usermod -aG docker ${USER}
```
