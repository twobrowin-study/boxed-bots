#!/bin/bash

echo "Creating certs services dirs..."
{% for service, service_cert_dir in certs.services_dirs.items() %}
    echo "Creating dir {{ service_cert_dir }} for service {{ service }}"
    mkdir -p "{{ service_cert_dir }}"
{% endfor %}

echo "Coping certificates into services dirs..."
{% for service, service_cert_dir in certs.services_dirs.items() %}
    echo "Copiing privkey and fullchain into {{ service_cert_dir }} for service {{ service }}"
    cp -L "{{ certs.privkey_path }}" "{{ service_cert_dir }}"
    cp -L "{{ certs.fullchain_path }}" "{{ service_cert_dir }}"
{% endfor %}

if [ "$EUID" -eq 0 ]
then
    echo "Setting certificates to own by {{ ansible_user }}..."

{% for service, service_cert_dir in certs.services_dirs.items() %}
    echo "Seting owner and policy of dir {{ service_cert_dir }} to be {{ ansible_user }} for service {{ service }}"
    chown -R "{{ ansible_user }}" "{{ service_cert_dir }}"
    chmod -R 0755 "{{ service_cert_dir }}"
{% endfor %}
fi
