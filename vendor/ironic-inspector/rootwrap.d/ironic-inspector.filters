# This file should be owned by (and only-writeable by) the root user

[Filters]
# ironic-inspector-rootwrap command filters for firewall manipulation
# ironic_inspector/pxe_filter/iptables.py
iptables: CommandFilter, iptables, root
ip6tables: CommandFilter, ip6tables, root

# ironic-inspector-rootwrap command filters for systemctl manipulation of the dnsmasq service
# ironic_inspector/pxe_filter/dnsmasq.py
systemctl: RegExpFilter, /bin/systemctl, root, systemctl, .*, openstack-ironic-inspector-dnsmasq.service
