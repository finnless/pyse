#include <stdint.h>
#include <string.h>

#define WIDTH 256
#define HEIGHT 192
#define SCREEN_SIZE (WIDTH/8 * HEIGHT)
#define SCREEN_BASE 0x4000
#define SCREEN (uint8_t*)SCREEN_BASE


// reduce computation by computing a smaller region
#define REGION_SIZE 100
#define REGION_X ((WIDTH - REGION_SIZE)/2)
#define REGION_Y ((HEIGHT - REGION_SIZE)/2)

uint16_t get_screen_offset(uint8_t y, uint8_t x) {
	return ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | (x >> 3);
}

void set(uint8_t* screen, uint8_t x, uint8_t y, uint8_t value) {
	if (x >= WIDTH || y >= HEIGHT) return;
	uint8_t* px = (uint8_t*)(screen + get_screen_offset(y, x));
	if (value) {
		*px |= 0x80 >> (x & 0x7);
	} else {
		*px &= ~(0x80 >> (x & 0x7));
	}
}

int get(uint8_t* screen, uint8_t x, uint8_t y) {
	if (x >= WIDTH || y >= HEIGHT) return 0;
	uint8_t* px = (uint8_t*)(screen + get_screen_offset(y, x));
	return (*px & (0x80 >> (x & 0x7))) != 0;
}

static inline int get_pixel(uint8_t* screen, int x, int y) {
	uint16_t offset = ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | (x >> 3);
	return (screen[offset] & (0x80 >> (x & 0x7))) ? 1 : 0;
}

static inline int count_neighbors(uint8_t* screen, int x, int y) {
	return get_pixel(screen, x-1, y-1)
		 + get_pixel(screen, x,   y-1)
		 + get_pixel(screen, x+1, y-1)
		 + get_pixel(screen, x-1, y)
		 + get_pixel(screen, x+1, y)
		 + get_pixel(screen, x-1, y+1)
		 + get_pixel(screen, x,   y+1)
		 + get_pixel(screen, x+1, y+1);
}

void update_generation(uint8_t* backup) {
	memcpy(backup, (uint8_t*)SCREEN_BASE, SCREEN_SIZE);

	for (int y = REGION_Y; y < REGION_Y + REGION_SIZE; y++) {
		for (int x = REGION_X; x < REGION_X + REGION_SIZE; x++) {
			int alive = get(backup, x, y);
			int neighbors = count_neighbors(backup, x, y);
			
			if ((alive && (neighbors == 2 || neighbors == 3)) || 
				(!alive && neighbors == 3)) {
				set(SCREEN, x, y, 1);
			} else {	
				set(SCREEN, x, y, 0);
			}
		}
	}
}

int main(void) {
	static uint8_t backup[SCREEN_SIZE];

	// The screen is probably clear, but just in case...
	memset(SCREEN, 0, SCREEN_SIZE);
	
	const uint8_t center_x = WIDTH/2;
	const uint8_t center_y = HEIGHT/2;
	const uint8_t radius = 10;
	
	// STARTING CONFIGURATION

	// Draw a border around the region
	for (int x = REGION_X; x < REGION_X + REGION_SIZE; x++) {
		set(SCREEN, x, REGION_Y, 1);
		set(SCREEN, x, REGION_Y + REGION_SIZE - 1, 1);
	}
	for (int y = REGION_Y; y < REGION_Y + REGION_SIZE; y++) {
		set(SCREEN, REGION_X, y, 1);
		set(SCREEN, REGION_X + REGION_SIZE - 1, y, 1);
	}



	// ATTRIBUTION: CLAUDE 3.5 for this circle drawing algorithm
	
	int x = radius;
	int y = 0;
	int err = 0;
	
	while (x >= y) {
		set(SCREEN, center_x + x, center_y + y, 1);
		set(SCREEN, center_x + y, center_y + x, 1);
		set(SCREEN, center_x - y, center_y + x, 1);
		set(SCREEN, center_x - x, center_y + y, 1);
		set(SCREEN, center_x - x, center_y - y, 1);
		set(SCREEN, center_x - y, center_y - x, 1);
		set(SCREEN, center_x + y, center_y - x, 1);
		set(SCREEN, center_x + x, center_y - y, 1);
		
		y += 1;
		err += 1 + 2*y;
		if (2*(err-x) + 1 > 0) {
			x -= 1;
			err += 1 - 2*x;
		}
	}

	// END ATTRIBUTION


	while(1) {
		update_generation(backup);
	}
}
