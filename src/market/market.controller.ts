import { Body, Controller, Get, Put } from '@nestjs/common';
import { EditMarketDto } from 'src/market/dto/edit-market-dto';
import { MarketService } from 'src/market/market.service';

@Controller('market')
export class MarketController {
  constructor(private readonly marketService: MarketService) {}

  @Get()
  findAll() {
    return this.marketService.findAll();
  }

  @Put()
  update(@Body() editMarketDto: EditMarketDto[]) {
    return this.marketService.update(editMarketDto);
  }
}
