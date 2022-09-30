blockDomains=$(</home/pi/git/tools/pihole/blocklist)

for domain in ${blockDomains[@]}; do
  pihole --wild -d $domain
done