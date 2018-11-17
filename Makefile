default:
	cp runCDN.py runCDN
	chmod +x runCDN
	cp stopCDN.py stopCDN
	chmod +x stopCDN
	cp deployCDN.py deployCDN
	chmod +x deployCDN
	$(MAKE) -C CDN

clean:
	rm -f runCDN
	rm -f stopCDN
	rm -f deployCDN
	$(MAKE) -C CDN clean