while true; do
	sleep 1
	gpioset -c gpiochip0 23=1
	sleep 1
	gpioset -c gpiochip0 23=0
	sleep 1000
done
