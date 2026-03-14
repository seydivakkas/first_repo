import { orderService } from './order.service';

export const paymentService = {
  pay(orderId: string, _gatewayToken: string) {
    return { message: 'Payment successful', order: orderService.markPaid(orderId) };
  }
};
