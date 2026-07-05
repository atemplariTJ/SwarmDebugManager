FROM ubuntu:22.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      openssh-server \
      bash \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash robot \
    && echo "robot:robot" | chpasswd \
    && mkdir -p /run/sshd \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

COPY fake-ros2 /usr/local/bin/ros2
COPY robot-entrypoint.sh /usr/local/bin/robot-entrypoint.sh
RUN chmod +x /usr/local/bin/ros2 /usr/local/bin/robot-entrypoint.sh

EXPOSE 22
CMD ["/usr/local/bin/robot-entrypoint.sh"]
