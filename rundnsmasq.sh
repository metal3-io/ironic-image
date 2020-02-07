#!/usr/bin/bash

. /bin/ironic-common.sh

export HTTP_PORT=${HTTP_PORT:-"80"}
DNSMASQ_EXCEPT_INTERFACE=${DNSMASQ_EXCEPT_INTERFACE:-"lo"}

wait_for_interface_or_ip

# If $DHCP_ALLOWLIST is set, filter out any mac's other
# than those specified. Works better than dnsmasq's
# dhcp-host feature, which expects to use the DUID instead
# of MAC's for DHCPv6 clients.
if [[ -n "$DHCP_ALLOWLIST" ]]; then
  iptables -t raw -N DHCP
  iptables -t raw -A PREROUTING -p udp --dport 67 -j DHCP
  iptables -t raw -A PREROUTING -p udp --dport 546 -j DHCP

  for mac in $(echo $DHCP_ALLOWLIST | sed 's/,/ /g')
  do
    iptables -t raw -A DHCP -m mac --mac-source "$mac" -j ACCEPT
  done

  iptables -t raw -A DHCP -j DROP
fi

mkdir -p /shared/tftpboot
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg

# Copy files to shared mount
cp /tftpboot/undionly.kpxe /tftpboot/ipxe.efi /tftpboot/snponly.efi /shared/tftpboot

# Template and write dnsmasq.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' </etc/dnsmasq.conf.j2 >/etc/dnsmasq.conf

for iface in $( echo "$DNSMASQ_EXCEPT_INTERFACE" | tr ',' ' '); do
    sed -i -e "/^interface=.*/ a\except-interface=${iface}" /etc/dnsmasq.conf
done

/bin/runhealthcheck "dnsmasq" &>/dev/null &
exec /usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf
