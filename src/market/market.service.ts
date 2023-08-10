import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { EditMarketDto } from 'src/market/dto/edit-market-dto';
import { Market } from 'src/market/entities/market.entity';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class MarketService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Market) private readonly market: Repository<Market>,
  ) {}

  async findAll() {
    return (await this.market.find()).sort((a, b) => a.id - b.id);
  }

  async findOne(id: number) {
    return await this.market.find({ where: { id } });
  }

  async update(editMarketDto: EditMarketDto[]) {
    return Promise.all(
      editMarketDto.map((_market) => this.market.save(_market)),
    );
  }
}
