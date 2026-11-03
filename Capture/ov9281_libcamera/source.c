// ov9281_trigger_debug.c
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/i2c-dev.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define OV9281_I2C_ADDRESS 0x60

struct ov9281_reg8 {
    uint16_t reg;
    uint8_t value;
};

static void print_errno(const char *action)
{
    fprintf(stderr, "[ov9281] ERROR: %s: %s (errno=%d)\n",
            action, strerror(errno), errno);
}

static int write_reg8(int fd, uint16_t reg, uint8_t value)
{
    const uint8_t message[3] = {
        (uint8_t)(reg >> 8),
        (uint8_t)(reg & 0xff),
        value,
    };

    printf("[ov9281] write: reg=0x%04X value=0x%02X"
           " bytes=[%02X %02X %02X]\n",
           reg, value, message[0], message[1], message[2]);

    ssize_t written = write(fd, message, sizeof(message));
    if (written == (ssize_t)sizeof(message)) {
        printf("[ov9281] write: success\n");
        return 0;
    }

    if (written >= 0) {
        errno = EIO;
        fprintf(stderr,
                "[ov9281] ERROR: partial I2C write: expected 3 bytes, got %zd\n",
                written);
    }

    print_errno("writing OV9281 register");
    return -errno;
}

int ov9281_set_trigger_mode(int i2c_bus, bool enable)
{
    static const struct ov9281_reg8 trigger_on[] = {
        { 0x3006, 0x0c },
        { 0x3027, 0x00 },
        { 0x4f00, 0x01 },
        { 0x3030, 0x04 },
        { 0x303f, 0x01 },
        { 0x302c, 0x00 },
        { 0x302f, 0x7f },
        { 0x3023, 0x00 },
        { 0x0100, 0x00 },
    };

    static const struct ov9281_reg8 trigger_off[] = {
        { 0x3006, 0x04 },
        { 0x4f00, 0x00 },
        { 0x0100, 0x01 },
    };

    char device[32];
    snprintf(device, sizeof(device), "/dev/i2c-%d", i2c_bus);

    printf("[ov9281] opening %s\n", device);

    int fd = open(device, O_RDWR);
    if (fd < 0) {
        print_errno("opening I2C device");
        return -errno;
    }

    printf("[ov9281] opened %s: fd=%d\n", device, fd);
    printf("[ov9281] selecting slave 0x%02X with I2C_SLAVE_FORCE (0x%04X)\n",
           OV9281_I2C_ADDRESS, I2C_SLAVE_FORCE);

    // This exactly matches the original binary's ioctl request 0x0706.
    if (ioctl(fd, I2C_SLAVE_FORCE, OV9281_I2C_ADDRESS) < 0) {
        int error = errno;
        print_errno("selecting OV9281 I2C address");
        close(fd);
        return -error;
    }

    const struct ov9281_reg8 *registers;
    size_t register_count;

    if (enable) {
        puts("[ov9281] enabling trigger mode");
        registers = trigger_on;
        register_count = sizeof(trigger_on) / sizeof(trigger_on[0]);
    } else {
        puts("[ov9281] disabling trigger mode");
        registers = trigger_off;
        register_count = sizeof(trigger_off) / sizeof(trigger_off[0]);
    }

    for (size_t i = 0; i < register_count; ++i) {
        printf("[ov9281] step %zu/%zu\n", i + 1, register_count);

        int rc = write_reg8(fd, registers[i].reg, registers[i].value);
        if (rc < 0) {
            close(fd);
            return rc;
        }
    }

    if (close(fd) < 0) {
        print_errno("closing I2C device");
        return -errno;
    }

    puts("[ov9281] trigger-mode update completed successfully");
    return 0;
}

static int parse_number(const char *text, long *out)
{
    char *end = NULL;
    errno = 0;
    long value = strtol(text, &end, 0);

    if (errno != 0 || end == text || *end != '\0')
        return -1;

    *out = value;
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <i2c_bus> <enable>\n", argv[0]);
        fprintf(stderr, "Example: %s 10 1\n", argv[0]);
        return 2;
    }

    long bus_arg;
    long enable_arg;

    if (parse_number(argv[1], &bus_arg) < 0 || bus_arg < 0 || bus_arg > 255) {
        fprintf(stderr, "[ov9281] Invalid I2C bus: %s\n", argv[1]);
        return 2;
    }

    if (parse_number(argv[2], &enable_arg) < 0) {
        fprintf(stderr, "[ov9281] Invalid enable value: %s\n", argv[2]);
        return 2;
    }

    // Mirrors the original binary: it truncates the parsed value to one byte.
    bool enable = (uint8_t)enable_arg != 0;

    printf("[ov9281] bus=%ld requested_enable=%ld effective_enable=%d\n",
           bus_arg, enable_arg, enable);

    int rc = ov9281_set_trigger_mode((int)bus_arg, enable);
    if (rc < 0) {
        fprintf(stderr, "[ov9281] FAILED: %s\n", strerror(-rc));
        return 1;
    }

    return 0;
}
