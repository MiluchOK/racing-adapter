#ifndef LED_LINKED_LIST_H
#define LED_LINKED_LIST_H

struct LedNode {
  uint8_t row;
  uint8_t col;
  LedNode* next;

  LedNode(uint8_t r, uint8_t c) : row(r), col(c), next(nullptr) {}
};

class LedLinkedList {
public:
  LedNode* head;

  LedLinkedList() : head(nullptr) {
    LedNode* tail = nullptr;

    // Create nodes for all 96 LEDs (8 rows x 12 cols)
    for (uint8_t row = 0; row < 8; row++) {
      for (uint8_t col = 0; col < 12; col++) {
        LedNode* node = new LedNode(row, col);

        if (head == nullptr) {
          head = node;
          tail = node;
        } else {
          tail->next = node;
          tail = node;
        }
      }
    }
  }

  ~LedLinkedList() {
    LedNode* current = head;
    while (current != nullptr) {
      LedNode* next = current->next;
      delete current;
      current = next;
    }
  }
};

#endif
