import { Controller, Get } from '@nestjs/common';
import { MarketService } from 'src/market/market.service';

@Controller('market')
export class MarketController {
  constructor(private readonly marketService: MarketService) {}

  @Get()
  findAll() {
    return this.marketService.findAll();
  }
}
